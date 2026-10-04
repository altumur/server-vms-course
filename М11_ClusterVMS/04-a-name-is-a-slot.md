# Урок 4 — Имя — это слот

**Модуль:** М11 — ClusterVMS: воркеры, которые переживают свой сервер
**Вы напишете:** имя воркера, которое даёт юнит, а доказывает запись в хранилище; разбор того, что происходит, когда с одним именем приходят два процесса; счёт недостачи и предложения слотов, которые публикует контроллер, и скрипт, который по ним запускает запасные процессы на хосте; и три случая жизни воркера — добавили, убрали, упал — и списание сервера, по трассам стенда.
**Время:** ~150 минут.

## Зачем этот урок

На каждом сервере кластера юнит даёт воркеру имя — `w-%l-1`, `w-srv-a-1` на `srv-a` (урок 3). Имя выглядит в точности как имя воркера. Соблазн — на этом и закончить. Этот урок объясняет, почему так нельзя, и что делает имя воркера надёжным.

Ставка высокая. Камеры назначены **воркеру по имени**: строка `vms/workers/w-srv-a-1` говорит «у `w-srv-a-1` камеры 1, 5 и 9». Если перезапущенный воркер придёт с другим именем, эти камеры останутся в строке, которую никто не читает. А если придут двое с одним именем — у камер будет два писателя, и архив это запомнит.

Второй вопрос урок М10B оставил открытым: **кто решает, сколько воркеров нужно.** Не контроллер — у него нет права запускать процессы, и это намеренно. Оркестратора, который держал бы число процессов, здесь нет (урок 1). Поэтому обязанности разведены так: контроллер **считает**, скольких воркеров не хватает, и пишет для них **предложения слотов**; скрипт на хосте, `w2c-spares.sh`, читает это число и **запускает** запасные; запасной берёт предложение по CAS; `systemd` перезапускает упавшее. Этот урок показывает все четыре движения по трассам.

> **Что проверяется без железа.** Всё. `tests/test_lesson2_jobs.py` — имя из юнита и метки сервера, запасной берёт предложение и останавливается, два процесса с одним именем, права по сокету; `vmsserver/tests/test_spares.py` — счёт, предложения, гонка двух запасных; `vmsserver/tests/test_deploy_units.py` — скрипт запасных с поддельными `curl` и `systemd-run`. Трассы стенда: [`04-two-processes-one-name`](traces/04-two-processes-one-name.txt), [`04-what-the-spares-script-reads`](traces/04-what-the-spares-script-reads.txt), [`04-a-spare-takes-an-offer`](traces/04-a-spare-takes-an-offer.txt), [`04-an-offer-withdrawn`](traces/04-an-offer-withdrawn.txt), [`04-a-crash-releases-nothing`](traces/04-a-crash-releases-nothing.txt), [`04-decommission-a-server`](traces/04-decommission-a-server.txt).

## Что нужно знать заранее

- **Урок 3** — юниты, `WORKER_NAME=w-%l-1`, `TimeoutStopSec`.
- **М10A, урок 7** — слот: `vms/slots/<имя>`, `claim_slot(prefer)`, «отпущен» против «истёк», списание сервера.
- **М10A, урок 8** — контроллер и его единственное действие без спроса.
- **М10A, урок 6** — эпоха на камеру.

## Чему вы научитесь

1. Объяснить, почему имя из юнита — пожелание, а имя — запись в хранилище.
2. Прочитать трассу двух процессов с одним именем и показать, где старый отсекается дважды — и кем он становится потом.
3. Сказать, кто решает число воркеров, прочитать числа, которые публикует контроллер, и объяснить, почему считается загрузка, а не процессор.
4. Объяснить, зачем запасному **предложение** слота и почему два скрипта на двух серверах не поднимут лишнего.
5. Проследить по трассам, что делает контроллер, когда воркер добавили, когда убрали и когда он упал, — и почему он **не** помогает упавшему.

---

## Шаг 1 — Слот: имя, доказанное записью

Имя воркера — это строка в хранилище:

```
vms/slots/w-srv-a-1   {"holder": "srv-a:4101", "until": "1757500045.0", "released": "false", "gen": "1"}
```

| Поле | Что значит |
|---|---|
| `holder` | какой экземпляр держит имя — `хост:pid:…` процесса (на стенде короче: `srv-a:4101`) |
| `until` | до какого момента держит; держатель продлевает его каждый шаг аренд |
| `released` | отпустил ли держатель имя сам, при плановой остановке |
| `gen` | поколение: растёт на единицу каждый раз, когда имя берёт новый экземпляр |

Хорошая аналогия — бейдж на проходной, выписанный на один день. Имя на бейдже — `w-srv-a-1`; кто им сейчас пользуется, записано в журнале охраны (`holder`); бейдж действует до конца смены (`until`), и его каждый раз продлевают. Сотрудник, уходя, сдаёт бейдж (`released: true`) — и охрана знает, что он ушёл. Сотрудник, которому стало плохо в коридоре, бейдж не сдаёт; бейдж просто истекает в конце смены, и охрана понимает: его нет, но почему — не знает.

Три состояния имени — и все три различимы по строке:

| Состояние | Строка | Что это значит |
|---|---|---|
| **держится** | `released: false`, `until` в будущем | воркер жив и работает |
| **отпущено** | `released: true` | воркер ушёл сам и сказал об этом — плановая остановка |
| **истекло** | `released: false`, `until` в прошлом | воркер молчит; упал он, завис или его сервер умер — по строке неизвестно |

Различие между «отпущено» и «истекло» — главное в этом уроке, и в шаге 7 станет понятно почему. Есть и четвёртый вид строки слота — **предложение**: пустой слот с полем `offer`, который может взять только запасной процесс (шаг 5).

## Шаг 2 — Имя из юнита — это пожелание

Юнит кладёт в окружение `WORKER_NAME=w-%l-1`, и `runtime.slot` отдаёт его воркеру (урок 3). Это имя, которое воркер попробует взять. Берёт он его так ([`w2cplatform/contract.py`](../vmsserver/w2cplatform/contract.py), `Worker._claim_slot`, в сокращении):

```python
            if prefer is not None:
                order = [prefer]
            else:
                lapsed = ...                                   # сначала истёкшие: их назначение ждёт
                free = ...                                     # потом свободные
                nxt = f"{self.SLOT_PREFIX}-{max([slot_number(n) for n in names] + [0]) + 1}"
                order = lapsed + free + [nxt]                  # и в конце — новый номер
            for cand in order:
                items, idx = self.vars.get(prefix + cand)
                cur = read_slot(prefix + cand, cand, items)
                ...
                if prefer is None and not cur.claimable(now):
                    continue
                new = Slot(cand, self.instance, now + self.slot_ttl, False, cur.gen + 1)
                try:
                    self.vars.put(prefix + cand, new.to_items(), cas=idx)
                except Conflict:
                    continue                                   # кто-то взял между чтением и записью
                self._slot_seen.pop(cand, None)
                self.slot, self.name = new, cand
                return cand
```

Три правила в этих строках.

**С пожеланием слот берётся, даже если его держит живой экземпляр.** Юнит сказал «это имя — твоё», и в вопросе, какой процесс текущий, супервизор — авторитет. Если `systemd` поднял процесс заново, старый экземпляр — это прошлое, даже если он ещё не знает об этом. Он узнает при следующем продлении (шаг 3). Но за именем идёт не всякое место: холд сетевого тома регистратора идёт за именем сразу только на той же машине (`BOX_ID=%m`, урок 3); процесс на другой машине ждёт холд `slot_ttl + HOLD_SKEW` по своим часам, если прежний не отпустил его сам: тот мог быть заморожен со смонтированным писателем (шестое ревью М10, блокер 2).

**Без пожелания сначала берутся истёкшие слоты.** Процесс, пришедший без имени, не должен заводить новое, пока есть истёкшее: у истёкшего слота в назначении лежат камеры, которые ждут. Кроме имени **зависшего** воркера: его процесс ещё работает на отвечающем сервере, и тот, кто взял бы его имя, взял бы и его камеры — второго писателя (шаг 7).

**Предложение не берёт никто, кроме запасного.** `Slot.claimable` для строки с `offer` ложен — обычный процесс проходит мимо (шаг 5).

Во всех случаях запись идёт по CAS. Два экземпляра, которые одновременно хотят одно имя, придут к одной записи с одной версией в `cas`, и хранилище пропустит одного.

## Шаг 3 — Два процесса с одним именем

Это случается не только по ошибке. Юнит перезапустили, а старый процесс ещё жив: завис так, что не дослушал `SIGTERM`, или заморожен, или до него не дошла остановка. Или оператор запустил вторую копию руками, с тем же окружением. Для слота все случаи одинаковы.

Трасса — [`traces/04-two-processes-one-name.txt`](traces/04-two-processes-one-name.txt). На стенде `w-srv-a-1` держит процесс `srv-a:4101`, у него камеры 1 и 2, эпохи 1. Приходит второй процесс, `srv-a:4102`, с тем же именем — и строка `#` у них одна и та же, `vmsworker w-srv-a-1 on srv-a`: отличить их можно только по `holder`.

Второй читает слот — его держит первый — и берёт его всё равно, по CAS с версией, которую прочитал:

```
# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
GET /v1/get?key=vms/slots/w-srv-a-1
→ 200 {
  "items": {
    "holder": "srv-a:4101",
    "until": "1757500045.0",
    "released": "false",
    "gen": "1",
    "server": "srv-a"
  },
  "index": 1008
}

# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-srv-a-1", "cas": 1008, "items": {
  "holder": "srv-a:4102",
  "until": "1757500045.0",
  "released": "false",
  "gen": "2",
  "server": "srv-a"
}}
→ 200 {"index": 1012}
```

`gen: 2` — новое поколение имени. Первый в это время продолжает работать и на следующем шаге аренд читает свой слот:

```
# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
GET /v1/get?key=vms/slots/w-srv-a-1
→ 200 {
  "items": {
    "holder": "srv-a:4102",
    "until": "1757500045.0",
    "released": "false",
    "gen": "2",
    "server": "srv-a"
  },
  "index": 1012
}
```

`holder` — не он. Продлевать нечего, и первый отсекает себя целиком: останавливает все конвейеры и пишет в журнал `FENCED (slot w-srv-a-1 is held by another instance now)`. Записывать для этого ничего не нужно — он узнаёт, **прочитав**. Никто ему не сообщал.

Второй читает назначение `w-srv-a-1` и берёт эпохи своих камер:

```
# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
GET /v1/get?key=vms/workers/w-srv-a-1
→ 200 {"items": {"units": "1,2", "rev": "1"}, "index": 1009}

# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
GET /v1/get?key=vms/epoch/1
→ 200 {"items": {"epoch": "1"}, "index": 1010}

# vmsworker w-srv-a-1 on srv-a → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/epoch/1", "cas": 1010, "items": {"epoch": "2"}}
→ 200 {"index": 1013}
```

Эпоха камеры 1 стала 2. Это **второй** барьер. Даже если первый по какой-то причине не заметил потерю слота — завис между продлениями, — его эпоха 1 устарела: при следующем продлении аренды на камеру он увидит эпоху 2 и остановит её. А всё, что он успел записать, лежит под эпохой 1 и помечено как запись отсечённого писателя (урок 9). Двое писать одну камеру не могут: сначала их разводит слот, потом эпоха. Тест — `test_two_processes_with_one_name_resolve_at_the_cas`.

Отсюда правило, которое первый проект ClusterVMS записал как «номер аллокации использовать нельзя», — в словах этого модуля:

> **Имя из юнита — метка. Имя воркера — слот, взятый по CAS; юнит только говорит, какой слот брать.**

### Старый процесс: никто, и только своё имя

Что дальше со старым процессом? Отсечённый воркер не выходит: «отсечён» — не навсегда. Первая версия на следующем проходе отдавала имя и брала **другое**, по правилам шага 2: истёкший слот, свободный — или новый номер. На стенде он становился `w-2` (номер слота — число после последнего дефиса, у всех `w-<сервер>-1` оно 1, следующий — 2; поэтому и предложения слотов, шаг 5, называются `w-2`, `w-3`). После двух процессов с одним именем на сервере оказывался **второй воркер**, о котором юнит не знает: контроллер видел его heartbeat и давал ему камеры, а остановить его было делом человека.

Владелец решил иначе (4 октября; в продукте то же, `r24-names`). Процесс, имя которому дал юнит (`WORKER_NAME`, `<ROLE>_NAME`, `SLOT_INDEX`), — это имя, и другого он не берёт. Имя он запоминает при старте (`Worker.given`, в `claim_slot(prefer=…)`), а отсечённый просит на каждом шаге аренд **только его** — и только свободным или истёкшим (`w2cplatform/contract.py`, `_seek_slot`):

```python
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
```

`steal=False` — это и есть «у живого не отнимать». В самом захвате (`_claim_slot`) оно стоит рядом с проверкой другой коробки, о которой ниже:

```python
                if prefer is not None and cur.holder != self.instance:
                    if not steal and (not cur.claimable(now) or cur.lapsed(now) and self._held(cand, cur)):
                        raise _NameTaken(cand, cur.holder, cur.until)   # live, or lapsed with its process hung: its holder's
                    if steal and not cur.claimable(now):
                        refused = self._may_take_by_name(cand, cur.holder)
                        if refused is not None:
                            self._contend(cand, cur.holder, REFUSED)   # seen on /servers, not only in this box's log
                            raise refused
```

Пока имя держит живой экземпляр, старый процесс — **никто**: слота нет, heartbeat под именем не пишется, назначение не читается, эпох нет (всё, что огорожено, пока `seeking`, — М10A, урок 8). Один раз за эпизод он говорит в журнал тревогу `worker.name_taken` — кто держит имя и на какой коробке — и в лог:

```
<экземпляр>: its name vms/w-srv-a-1 is held by <держатель> (box <коробка>) — another process started under the same name took it. This one is nobody now: it holds nothing, and takes its name back when that is free; it takes no other
```

И оставляет метку `vms/contenders/w-srv-a-1/<коробка>` (объект, как heartbeat: `{name, state: "nameless", box, hostname, server, instance, holder, holder_box, since, at}`), переписывая её раз в `CONTEND_EVERY` (10 с) — его пульс, пока heartbeat под именем чужой. Новый держатель остановился (`SIGTERM` отпускает слот) или замолчал дольше срока слота — старый берёт своё имя и пишет `worker.name_back`. Отнимать имя у живого он не будет никогда: два живых процесса одного имени на одной коробке отнимали бы его друг у друга вечно. **И истёкшее имя он берёт только тогда, когда контроллер перенёс бы его камеры** (`Worker._held`; двенадцатое ревью, блокер 2): 45 секунд после конца слота (`SLOT_LOST_AFTER`) контроллер считает слот живым — то, что начал прежний процесс, может ещё писать, — и процесс без имени, взявший имя в этом окне, забирал вместе с ним камеры зависшего: проба ревьюера дала двух писателей на +46…+89 с. Теперь имя держится, пока `slot_fate` говорит `alive`, `hung` или `unsure`, а вопрос, на который хранилище не ответило, — «не знаю», и имя тоже держится (была «не завис»). Тесты: `vmsserver/tests/test_slot_fate.py::test_a_nameless_process_does_not_take_a_hung_workers_name_within_the_margin`, `::test_a_spare_that_cannot_ask_whether_the_holder_is_gone_leaves_the_name_alone`. Захват имени у живого держателя остался **только при старте** — это перезапуск после `kill -9`, где юнит знает, какой процесс настоящий. Процесс без имени (не дали ни имени, ни индекса) возвращается, как раньше, под свободным номером. Тесты: `vmsserver/tests/test_names.py` — `test_a_process_named_by_its_unit_whose_name_was_taken_is_nobody_and_takes_no_other_number`, `test_a_nobody_takes_its_name_once_the_holder_lapses_and_never_from_a_live_holder`, `test_a_process_that_took_whatever_was_free_still_rejoins_under_a_free_number`; на стенде модуля — `test_lesson4_failover.py::test_two_processes_with_one_name_the_old_one_is_nobody`.

### Свежая коробка: одно имя на двух машинах

И второй случай того же рода — **свежая коробка**. `%l` — это имя хоста. Две только что поставленные машины с именем по умолчанию (`localhost`, `debian`, два клона одной виртуальной машины) дают своим воркерам одно имя — `w-localhost-1` на обоих серверах, — хотя `SERVER_NAME` в `w2c.env` у них разный. Раньше каждый перезапуск одного отнимал имя у другого, а заметить это можно было только по логам двух машин.

Теперь живого держателя с **другой** коробки не трогают. Коробку экземпляр носит в своём имени: `<коробка>:<pid>:<6 hex>`, где коробка — `BOX_ID`, если его сказал рантайм, иначе идентификатор машины (`/etc/machine-id`), иначе имя хоста (`runtime.box`). Имя хоста одно на двух клонах — идентификатор машины у них разный. Правило — `Worker._may_take_by_name`:

```python
    def _may_take_by_name(self, slot: str, holder: str) -> "NameOnAnotherBox | None":
        here, there = runtime.box_of(self.instance), runtime.box_of(holder)
        if here is None or there is None or here == there:
            return None
        return NameOnAnotherBox(slot, holder, there, socket.gethostname(), here, getattr(self, "NAME_ENV", ""))
```

Та же коробка — это перезапуск, имя берётся. Имя, которое коробки не называет (`INSTANCE_ID`, идентификатор аллокации: такие имена даёт планировщик и сам переносит индекс между узлами), — тоже берётся, как раньше. Живой держатель с другой коробки — отказ: процесс пишет, что делать, и выходит, а юнит его перезапускает:

```
w-localhost-1 is held by a live process on another machine (box <коробка>, instance <держатель>): two machines are given one name, usually because they share the hostname 'localhost' (the units name their processes from it, w-%l-1). Give this machine another hostname, or set WORKER_NAME in its unit to a name no other machine uses. This machine (box <своя>) leaves the name alone: taking it would stop the other machine's live process
```

Каждый отказ переписывает метку `vms/contenders/<имя>/<коробка>` с `state: "refused"`; начало эпизода (`since`) берётся из прежней свежей метки, так что перезапуски юнита эпизод не множат. Метка, не обновлявшаяся `CONTENDER_FRESH` (300 с), не читается. Кто её видит:

- `/servers` — у строки держателя поле `name_conflict`: `{holder, holder_box, contenders: [{state, box, hostname, server, instance, holder_seen, since, for_s, at}]}`, `null`, пока никто не просит;
- контроллер — раз за эпизод тревога `worker.name_conflict` (`Controller.say_name_conflicts`, шаг прохода `name_conflicts`): кто держит, какая коробка просит, с какого момента;
- `/metrics` — `vms_name_conflicts`, число имён со свежей меткой (из отчёта прохода, поле `name_conflicts`).

Когда держатель с той коробки уходит и его слот истекает, следующий перезапуск берёт имя как истёкшее и метку убирает. Тест: `test_names.py::test_a_live_holder_on_another_box_keeps_its_name_and_the_refused_process_is_seen`. Имя хоста всё равно задают до `install.sh`: `hostnamectl set-hostname srv-a` — отказ лишь не даёт двум машинам драться за одно имя молча.

## Шаг 4 — Кто решает N

Никто в VMS не запускает процессов. Контроллер — **считает**. В конце каждого прохода, **после** того как он выполнил списания серверов, перенёс камеры мёртвых слотов и раздал камеры отпущенных (`SpecController.offer_spares`, последний шаг `pass_once`), он считает по каждому набору меток:

```
#   waiting       per label set (a unit's `labels` under `labels-subset`; "" for every unit otherwise): units with no
#                 placement, and units still on a worker that is leaving (`leaving`: a released slot, a silent
#                 resource, a drained or decommissioned server, a dead slot whose fate is `move`). Not a hung
#                 worker's, not a slot's before its fate says move — those are waited for, not short
#   free          the room (`capacity − load`) of the workers in the pool whose labels cover the set
#   units_short   waiting − free, at least 0. A set no live worker covers has no free room: short by itself
#   needed        ceil(units_short / per), at most the servers a spare of the set could carry units on, less the
#                 offers of the set a spare took and whose worker has not been heard yet — for `OFFER_GRACE` (90 s)
#                 from the take it is a worker on its way
```

**Предложение — только туда, где запасной понесёт камеры** (двенадцатое ревью, «Вопросы»: найдено при пересборке `three-cameras` запусками). Счёт не спрашивал трёх вещей. Ёмкость он делил на свою константу `CAPACITY`, а не на то, что скажет запасной; теперь `per` — наименьшая ёмкость, которую называют живые воркеры этого набора (запасной стартует тем же юнитом и окружением и скажет то же), константа — только когда живых нет. Предложения писались и для набора, который не покрывает ни один сервер, — они висели, никем не взятые. И под `servers: distinct` запасной, поднятый на сервере, где воркер уже есть, простаивал по политике (`idle_by_policy`), камера оставалась неразмещённой, а следующий проход предлагал снова — скрипты поднимали простаивающих запасных до `MAX_WORKERS` на каждом сервере. Теперь сервер, на котором запасной может встать (`SpecController._spare_hosts`), — не списан, не в drain, его ресурс не молчит, метки покрывают набор (строка консоли, иначе слово его воркеров; сервер, о метках которого никто ещё не сказал, может покрыть); под `distinct` — ещё и без живого воркера этой подсистемы. Не хватает таких серверов — предложений столько, сколько их есть, недостача остаётся в `units_short`, причина — в отчёте (`spares_withheld`) и на `/metrics` (`vms_spares_withheld{labels}`), тревога `spares.no_server` — раз за эпизод. Тесты: `vmsserver/tests/test_spares.py::test_no_offer_where_no_server_could_carry_a_spare`, `::test_under_distinct_servers_a_spare_is_offered_only_where_it_would_not_idle`, `::test_the_shortage_is_counted_by_what_the_workers_announce_not_the_controllers_fallback`.

Две вещи здесь стоят того, чтобы их прочитать дважды. **Считается после переносов**: смерть сервера не поднимает ни одного лишнего процесса, если живым хватает места, — камеры сначала расходятся по свободной ёмкости. **И не всё молчащее — недостача**: камеры зависшего воркера и камеры слота, судьба которого ещё не «переносить», — это ожидание, а не нехватка.

Консоль публикует эти числа на `/metrics` без токена, пока отчёт прохода контроллера не старше 60 секунд. Вот что она отдаёт, когда два воркера ёмкостью 4 несут восемь камер, а девятая просит сеть `vlan:cctv-b` ([`traces/04-what-the-spares-script-reads.txt`](traces/04-what-the-spares-script-reads.txt)):

```
GET /metrics
# TYPE vms_workers_live gauge
vms_workers_live 2
# TYPE vms_worker_load gauge
vms_worker_load{worker="w-srv-a-1"} 1.000
vms_worker_load{worker="w-srv-b-1"} 1.000
# TYPE vms_workers_needed gauge
vms_workers_needed{labels=""} 0
vms_workers_needed{labels="vlan:cctv-b"} 1
# TYPE vms_units_short gauge
vms_units_short{labels=""} 0
vms_units_short{labels="vlan:cctv-b"} 1
# TYPE vms_spare_offers gauge
vms_spare_offers{labels=""} 0
vms_spare_offers{labels="vlan:cctv-b"} 1
# TYPE vms_server_labels gauge
vms_server_labels{server="srv-a",labels="vlan:cctv-a",source="node"} 1
vms_server_labels{server="srv-b",labels="vlan:cctv-a,vlan:cctv-b",source="node"} 1
vms_server_labels{server="srv-c",labels="",source="node"} 1
```

Четыре ряда — те, что читает скрипт запасных. `vms_workers_needed` — сколько воркеров нужно, по набору меток (пустой набор есть всегда). `vms_units_short` — сколько камер не поместилось. `vms_spare_offers` — сколько предложений слотов ждёт. `vms_server_labels` — что видит каждый сервер: `source="node"` — метки из его окружения (`LABELS` в `w2c.env`, через heartbeat), `source="console"` — метки, которые администратор записал в консоли (М10A, урок 11); второе важнее первого. То же — `live_*` на `/live/metrics` и `auto_*` на `/auto/metrics`. Регистраторы остаются на своём числе, `rec_recorders_needed` на `/rec/metrics`: их раскладывают по томам, а не по меткам, — незанятый том требует ещё одного регистратора, даже если все существующие загружены.

**Почему загрузка, а не процессор.** `vms_worker_load` — это `1 − headroom/capacity`, прямо из heartbeat'ов (урок 1). Воркер с двумястами камерами в три часа ночи загружен на 12 % процессора — и **полон**: каждая из этих камер назначена и должна остаться назначенной. Счёт по процессору ночью решил бы, что воркеров много. Загрузка говорит, каков спрос: камеры, которым нужен воркер, делённые на то, что воркеры могут нести.

**Что регистратор говорит о себе — тоже числами.** Ограждённый регистратор и регистратор без назначений оба показывали «0 идёт». Том, который не открылся, ушедший архив и вставший писатель были в heartbeat'е и на странице, но повесить на них оповещение было не на что (обратная связь, BG). Консоль читает те же heartbeat'ы и отдаёт по каждому регистратору: `rec_recordings{worker,phase}`, `rec_volume_error{worker}`, `rec_archive_away_seconds{worker}`, `rec_writer{worker,state}`, `rec_archive_failure{worker,kind}`, а рядом общие для любой подсистемы `rec_worker_fenced` и `rec_worker_store_errors`. Ещё один ряд — по записи, а не по регистратору: `rec_last_frame_age_seconds{unit}`. `rec_recordings{phase="running"}` говорит, что конвейер поднят; этот ряд говорит, что в него что-то **приходит**. Своего порта у регистратора по-прежнему нет: его никто не вызывает, и спрашивать о нём надо там же, где обо всём остальном.

## Шаг 5 — Предложение слота и скрипт запасных

Число — полдела. Запасной процесс без имени не ищет свободный слот, а заводит **новый** (шаг 2, `nxt`): два скрипта на двух серверах подняли бы два процесса, оба взяли бы новые слоты, и камер хватило бы обоим — кластер вырос бы вдвое против нужного. Поэтому контроллер на каждый недостающий воркер пишет **предложение** — пустую строку слота с набором меток, для которого она:

```python
                self.vars.put(self.sub.slot_key(name), {"holder": "", "until": "0", "released": "false", "gen": "0",
                                                        "offer": labels, "offered_at": str(now)}, cas=0)
```

Запасной (`SPARE_FOR=<набор>`) берёт **только** предложение своего набора, по CAS; нет предложения — ждёт, ничего не держа: ни имени, ни heartbeat, ни камер. Обычный процесс предложений не берёт никогда. Два настоящих запасных на недостачу в один воркер — ровно один берёт слот, второй ждёт (`test_two_spares_racing_for_one_offer_exactly_one_takes_it_and_the_other_waits_holding_nothing`).

Запускает запасные скрипт [`vmsserver/deploy/w2c-spares.sh`](../vmsserver/deploy/w2c-spares.sh) — на хосте, от root, по таймеру `w2c-spares[-<роль>].timer` раз в минуту (`install.sh --spares`). Это размещение и есть смысл файла: запустить процесс — значит говорить с `systemd` от root, и консоль, которая умела бы это, была бы консолью с правами root на собственной машине. Правила скрипта — в его шапке:

```
#   1. It reads numbers, never a command. Running a string that arrived over HTTP as root is remote code execution
#      with extra steps, however friendly the source.
#   2. A console that does not answer, or whose controller's pass is older than a minute (the numbers are not on its
#      page then), is a reason to start NOTHING.
#   3. Only the label sets THIS server covers: a camera on `vlan:cctv-dmz` is no use to a worker on a server that does
#      not reach that VLAN. The server's labels are the console's (`<prefix>_server_labels{server=…,source="console"}`
#      — what the administrator wrote for it), else this host's `$LABELS`.
#   4. Its own ceiling per role, counting the spares already running here: a bug on the other side that reported
#      "nine hundred missing" costs a log line, not nine hundred processes.
#   5. A camera worker, gateway or evaluator starts as a SPARE (`SPARE_FOR=<label set>`): it takes only an offer of
#      its set (`<sub>/slots/<w-N>` with `offer`), by CAS, and with none it waits holding nothing — two scripts on two
#      servers racing for one missing worker start two spares, and exactly one takes the slot. A recorder needs no
#      offer: it is placed by volume, and a recorder with no free volume to hold is already a spare.
```

Роли — в `SPARES_ROLES` или аргументами, у каждой свой потолок: `recworker` (`MAX_RECORDERS`), `vmsworker` (`MAX_WORKERS`), `liveworker` (`MAX_GATEWAYS`), `autoworker` (`MAX_EVALUATORS`). Тесты скрипта — `test_the_spares_script_starts_spares_for_the_sets_its_server_covers_up_to_its_ceiling_and_stops_nothing` и `test_the_spares_script_takes_the_hosts_labels_without_a_console_row_and_starts_nothing_on_a_silent_or_stale_console`.

**Запасной — юнит своей роли, а не процесс root'а.** Раньше скрипт запускал запасного как `systemd-run … w2c-run.sh worker`: от root, без ключа кластера, с раздачей на петле. Камера умершего сервера с запечатанным паролем не стартовала на том самом процессе, который ради неё подняли (`open_row` бросал `Sealed`), регистратор других серверов не доставал до раздачи, а файлы в архиве событий получали хозяина root (двенадцатое ревью, блокер 6). Решение владельца: запасной запускается с теми же учётными данными, ключами, окружением, пользователем и группами, что юнит роли. Выбран **шаблон юнита**, а не `systemd-run` со списком свойств: шаблон — тот же файл рядом с юнитом роли, `systemctl cat` показывает его оператору, `%d` (каталог учётных данных) в нём раскрывается, а тест держит его строка в строку с юнитом роли (`test_units.py::test_a_spare_is_its_roles_unit_line_for_line_but_the_name`) — строку, добавленную роли и забытую у запасного, тест не пропустит. Список свойств в скрипте был бы вторым описанием роли, которое расходится молча. Шаблон отличается от юнита роли только тем, что нужно запасному: у него нет `WORKER_NAME`; набор меток он читает из файла в одну строку (`EnvironmentFile=/run/w2c-spares/%n.env`, без `-`: нет набора — нет и старта, иначе получился бы воркер, берущий любое свободное имя); раздача у воркера и дверь у регистратора — на порту, который даст ОС, потому что 8554 и 8084 у штатных процессов этого сервера. Скрипт пишет файл и делает `systemctl start vms-<роль>-spare@<n>`; шаблона нет — не запускает ничего и говорит почему (`test_deploy_units.py::test_a_spare_is_started_only_as_its_roles_unit_and_never_as_root_without_one`). На macOS шаблон — plist самой роли: скрипт копирует его как `com.w2c.vms.<роль>.spare-<n>`, без имени, с `SPARE_FOR` и своими портами, и делает `launchctl bootstrap` (`test_the_spares_script_on_macos_starts_its_roles_plist_without_the_name_and_counts_it_by_its_label`). Сам скрипт остаётся root: он запускает юниты.

**Он никого не гасит.** Запасной стоит несколько мегабайт и делает так, что **следующая** недостача обслужится за проход, а не за выезд. Решить, что процессов на коробке слишком много, — дело человека, намеренно.

## Шаг 6 — Добавили воркер, убрали воркер

Трасса — [`traces/04-a-spare-takes-an-offer.txt`](traces/04-a-spare-takes-an-offer.txt). В ней только записи: контроллер на каждом проходе перечитывает строки размещения и камер, и чтений там больше ста. Два воркера ёмкостью 4 несут восемь камер; оператор создаёт девятую, и места ей нет. Проход контроллера пишет предложение:

```
# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-2", "cas": "", "items": {
  "holder": "",
  "until": "0",
  "released": "false",
  "gen": "0",
  "offer": "",
  "offered_at": "1757500000.0"
}}
→ 200 {"index": 1048}
```

`"offer": ""` — пустой набор меток: камера ни о чём не просит. Скрипт на `srv-c` видит `vms_workers_needed{labels=""} 1` и поднимает `vms-vmsworker-spare@1` с `SPARE_FOR=` в его файле. Запасной берёт предложение — по CAS на ту версию, что прочитал:

```
# vmsworker spare on srv-c → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-2", "cas": 1048, "items": {
  "holder": "srv-c:4103",
  "until": "1757500045.0",
  "released": "false",
  "gen": "1",
  "offer": "",
  "offered_at": "1757500000.0",
  "taken_at": "1757500000.0",
  "server": "srv-c"
}}
→ 200 {"index": 1049}
```

`offer` и `offered_at` остались — по ним контроллер ещё 90 секунд считает этот слот «воркером в пути» и не просит второго; `taken_at` — когда взяли. На следующем проходе контроллер видит нового воркера по его heartbeat и ставит на него камеру 9 — две записи, размещение с причиной и назначение:

```
# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/placement/9", "cas": "", "items": {
  "worker": "w-2",
  "reason": "most free capacity (4) among 3 worker(s); on srv-c, whose resource is live",
  "at": "1757500000.0",
  "rev": "1"
}}
→ 200 {"index": 1050}

# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/workers/w-2", "cas": "", "items": {"units": "9", "rev": "1"}}
→ 200 {"index": 1051}
```

Причина написана для человека и говорит всё, что контроллер знал: выбран воркер с наибольшей свободной ёмкостью из трёх, он на `srv-c`, и ресурс этого сервера жив. Воркер читает своё назначение и берёт эпоху камеры:

```
# vmsworker spare on srv-c → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/epoch/9", "cas": "", "items": {"epoch": "1"}}
→ 200 {"index": 1052}
```

Контроллер **разместил** девятую камеру, когда появился воркер. Он посчитал недостачу и оставил предложение, но процесса не запускал и не знал, кто и где его запустит, — он прочитал heartbeat.

Теперь запасного останавливают: `systemctl stop vms-vmsworker-spare-1`. Он получает `SIGTERM` и отпускает слот:

```
# vmsworker spare on srv-c → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-2", "cas": 1049, "items": {
  "holder": "srv-c:4103",
  "until": "1757500000.0",
  "released": "true",
  "gen": "1"
}}
→ 200 {"index": 1053}
```

`released: true` и `until` — сейчас. Это и есть сданный бейдж. Контроллер на следующем проходе видит отпущенный слот и переносит его камеры туда, где есть место (оператор перед этим удалил камеры 1 и 2, освободив место на `w-srv-a-1`):

```
# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/placement/9", "cas": 1050, "items": {
  "worker": "w-srv-a-1",
  "reason": "slot w-2 released; most free capacity (1); on srv-a",
  "at": "1757500000.0",
  "rev": "2"
}}
→ 200 {"index": 1062}

# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/workers/w-2", "cas": 1051, "items": {"units": "", "rev": "2"}}
→ 200 {"index": 1063}
```

Камера 9 получает новое размещение с причиной «слот w-2 отпущен», назначение `w-2` пустеет, и камера появляется в назначении `w-srv-a-1`. Каждая запись — по CAS: второй контроллер, если он есть, не сделает ту же перестановку дважды (урок 10).

Вот почему у юнита `TimeoutStopSec=20`. Отпускание слота — запись по CAS, и она должна успеть до того, как `systemd` убьёт процесс. Не успела — остановка выглядит как падение.

**Предложение, которое больше не нужно.** Трасса — [`traces/04-an-offer-withdrawn.txt`](traces/04-an-offer-withdrawn.txt): предложение ждёт запасного, а недостача уходит раньше — оператор удалил камеру, и девятая поместилась на `w-srv-a-1`. Следующий проход снимает предложение — удалением по CAS на ту версию, которую он прочитал:

```
# vmscontroller on srv-b → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "delete", "key": "vms/slots/w-2", "cas": 1048}
→ 200 {"index": 1055}
```

По CAS — потому что запасной мог взять его между чтением и удалением. Тогда его запись сдвинула версию, удаление получает `409`, и взятое предложение остаётся тому, кто взял (`test_an_offer_not_needed_any_more_is_removed_by_the_controller`).

## Шаг 7 — Упал воркер

Трасса — [`traces/04-a-crash-releases-nothing.txt`](traces/04-a-crash-releases-nothing.txt). `w-srv-c-1` держит камеру 1 и умирает, ничего не сказав. Через две секунды `systemd` поднимает его юнит снова (`Restart=always`, `RestartSec=2`). Между этим контроллер делает свой проход и читает слот:

```
# vmscontroller on srv-a → /run/configstore/vmscontroller.sock
GET /v1/get?key=vms/slots/w-srv-c-1
→ 200 {
  "items": {
    "holder": "srv-c:4101",
    "until": "1757500045.0",
    "released": "false",
    "gen": "1",
    "server": "srv-c"
  },
  "index": 1006
}
```

`released: false`, срок ещё не вышел — для контроллера имя держится. И контроллер **не пишет ничего**. В трассе после этого чтения от него нет ни одной записи.

Новый процесс того же юнита берёт `w-srv-c-1` — с пожеланием, по CAS, — и находит назначение на месте:

```
# vmsworker w-srv-c-1 on srv-c → /run/configstore/vmsworker.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-srv-c-1", "cas": 1006, "items": {
  "holder": "srv-c:4102",
  "until": "1757500047.0",
  "released": "false",
  "gen": "2",
  "server": "srv-c"
}}
→ 200 {"index": 1010}

# vmsworker w-srv-c-1 on srv-c → /run/configstore/vmsworker.sock
GET /v1/get?key=vms/workers/w-srv-c-1
→ 200 {"items": {"units": "1", "rev": "1"}, "index": 1008}
```

Назначение на месте: камера 1 ждала своего воркера — и дождалась. Перезапуск не переписал ни одной строки конфигурации. Это центральная мысль модуля: **камера назначена воркеру `w-srv-c-1` в хранилище, а не процессу и не серверу**, поэтому новый процесс читает то же назначение из того же хранилища.

Почему контроллер не «помог», переставив камеру при первом молчании? Потому что молчание не говорит, что случилось. Процесс мог упасть — тогда `systemd` через секунды поднимет его, и он найдёт пустое назначение: камеры переехали бы дважды без всякой пользы. Процесс мог зависнуть или потерять сеть на полминуты — тогда на время путаницы у камеры было бы два писателя. Отпущенный слот — это **утверждение** держателя; истёкший — всего лишь **отсутствие** утверждения.

Третье утверждение может сделать сервер. Каждый воркер регистрируется у ресурса своего сервера (`Worker.present`): держит замок `<дерево ресурса>/.workers/<экземпляр>.lock`, пока жив его процесс. **В кластере этого не было.** Точки входа М11 строили воркер и регистратор и регистрацию не вызывали — коробка вызывала (`vms/__main__._present`), кластер нет (двенадцатое ревью, «Вопросы», дефект 1). Пульс каждого ресурса говорил `workers` и `running` пустыми, мёртвый процесс на живом сервере получал исход `wait` — «нельзя сказать» — навсегда, и если `systemd` его не поднимал, камеры не писал никто. Теперь процесс строят и регистрируют одни функции, `cluster.__main__.make_worker` и `make_recorder`, — их зовут и юниты, и стенд модуля, поэтому стенд запускает ровно то, что юнит:

```python
def make_worker(vars_, objects, actuator=None, env: dict | None = None, **kw):
    from cluster.worker import ClusterWorker
    w = ClusterWorker(vars_, objects, actuator, env=env, **kw)
    w.present(w.archive_root)                  # its server's resource tree: where its events go too
    return w
```

Тесты — `test_lesson4_failover.py::test_every_unit_registers_with_its_servers_resource_and_a_process_that_ended_moves_when_its_slot_runs_out` (ресурс `srv-a` называет воркер и регистратор размещёнными и запущенными; завис — камеры остаются; процесс кончился — камеры переезжают на этом же проходе) и `::test_the_worker_entry_point_registers_its_process_before_it_runs` (сама точка входа `worker()`). Ресурс в пульсе говорит, какие воркеры у него размещены (`workers`) и чьи процессы работают (`running`, замок занят). По этим словам контроллер решает судьбу истёкшего слота (`Controller.slot_fate`):

- **процесс мёртв, ресурс жив и говорит это** — камеры переезжают, как только истёк срок слота (45 с), без запаса `SLOT_LOST_AFTER` поверх: мёртвый процесс ничего не пишет (решение владельца от 3 октября);
- **процесс жив, но не продлевает и не пишет пульс** — завис: камеры остаются у него, чтобы не дать им второго писателя, до `HUNG_MOVE_AFTER` (15 минут), с тревогой `worker.hung`; предел — контроллера, он пишет его в отчёт прохода (`hung_move_after`), и запасной судит по нему, а не по своему умолчанию (`test_a_spare_and_the_console_judge_a_hung_worker_by_the_controllers_limit_not_their_own`);
- **молчит и ресурс** — сервер умер или отрезан: камеры переезжают после срока слота и запаса, ~90 с.

Числа переезда, их замер и учения — урок 8.

## Шаг 8 — Списание сервера

Для оператора, который знает то, чего не знает система, — сервер не вернётся, его вывезли, — есть **списание сервера**. Слово человека здесь о машине, а не о процессе (решение владельца курса после одиннадцатого ревью). Раньше на этом месте стояла дверь `POST /workers/<w>/retire`: оператор снимал молчащий воркер, а молчащий мог быть зависшим, чьи конвейеры ещё писали, — и у его камер оказывалось два писателя. Ту дверь убрали. Теперь в блоке сервера на странице есть ссылка *decommission*, и она шлёт `POST /servers/srv-c/decommission {"why": "…"}`. Пока srv-c отвечает — слышен его ресурс, слышен его воркер или воркер продлевает слот, — консоль отвечает 409, называет признак словами и ничего не пишет. Когда сервер молчит, консоль пишет одну строку, `platform/decommission/srv-c {by, at, why}`, и строку в журнал (`server.decommission_requested`). Слоты она не трогает: сокету консоли запрещено писать `vms/slots/*` (урок 5). Контроллер на следующем проходе (`pass_once`, первый шаг — `apply_decommissions`) освобождает слоты этого сервера через CAS и пишет отметку `vms/decommissioned/srv-c {asked_at, at, slots, units, holds}`. Трасса [`traces/04-decommission-a-server.txt`](traces/04-decommission-a-server.txt) (сгорел srv-c под `w-srv-c-1`) — первые две записи, от двух процессов:

```
# console on srv-a → /run/configstore/console.sock
POST /v1/write {"op": "put", "key": "platform/decommission/srv-c", "cas": null, "items": {
  "by": "anna",
  "at": "1757500100.0",
  "why": "srv-c burnt"
}}
→ 200 {"index": 1016}

# vmscontroller on srv-a → /run/configstore/vmscontroller.sock
POST /v1/write {"op": "put", "key": "vms/slots/w-srv-c-1", "cas": 1009, "items": {
  "holder": "srv-c:4102",
  "until": "1757500045.0",
  "released": "true",
  "gen": "1"
}}
→ 200 {"index": 1017}
```

Консоль написала строку о сервере, а не слот. Слот пишет контроллер, и его CAS стоит на той строке, которую он только что проверил. Дальше в той же трассе камера 2 уезжает на `w-srv-b-1` с причиной `slot w-srv-c-1 released; most free capacity (49); on srv-b`. На srv-c больше ничего не размещается, и процессу на нём не дают слот, пока оператор не вернёт его (`DELETE /servers/srv-c/decommission`) — именно об этом спрашивает каждый воркер при старте (урок 1, шаг 6). Тома, которые держал воркер (`rec/holds/*`), освобождение слота не отпускает, и консоль их называет. Подробно — в М10A, урок 7, шаг 7. Права на эту строку — в уроке 5.

---

## Результат

- Запасной на `srv-c` взял предложение, и следующая камера размещена на нём за один проход; контроллер не запустил ни одного процесса.
- `systemctl stop` запасного — слот отпущен, камеры отпущенного слота перенесены.
- Убитый `kill -9` воркер: `systemd` поднял его через 2 с, контроллер не сделал ничего, новый процесс взял то же имя и то же назначение.
- Шесть трасс урока, в каждой из которых вы показываете решающую запись.

## Что может пойти не так

- **Две машины с одним именем хоста.** Одно `w-%l-1` на двух серверах: держит тот, кто взял первым, второй выходит со словами и перезапускается юнитом; `/servers` показывает `name_conflict`, контроллер — тревогу `worker.name_conflict`, `vms_name_conflicts` 1. Задайте имя хоста (или `WORKER_NAME` в юните) до установки.
- **Процесс, который держит ничего и пишет `worker.name_taken`.** Старый процесс после двух процессов с одним именем на одной коробке: ждёт своё имя и другого не берёт. Если он не нужен — остановите его `SIGTERM`; если нужен он, а не новый, — остановите новый, и старый возьмёт имя сам.
- **Плановая остановка оставила слот `released: false`.** `TimeoutStopSec` слишком короткий, или процесс не обрабатывает `SIGTERM`. 20 секунд, и выход обязан идти через `release_slot()`.
- **Запасной, запущенный руками без `SPARE_FOR`.** Это не запасной, а обычный процесс: он заведёт новый слот вместо предложения, и камер станет хватать двоим.
- **Скрипт запасных, который гасит «лишние».** Гонка с недостачей следующего прохода; остановка — решение человека.
- **Счёт по процессору.** Ночью кластер «пустой», хотя все места заняты. Считается загрузка: назначено ÷ ёмкость.
- **Контроллер переносит камеры при первом молчании воркера.** Двойной переезд или два писателя; повод — отпущенный слот, мёртвый процесс по слову ресурса или молчащий сервер.

## Итог

- Имя воркера — строка `vms/slots/<имя>`: держатель, срок, «отпущен», поколение; записывается по CAS.
- Имя из юнита — пожелание: с ним слот берётся даже у живого держателя, потому что супервизор — авторитет в вопросе, какой процесс текущий.
- Два процесса с одним именем разводятся дважды: слотом (старый узнаёт при продлении) и эпохой (его записи помечены отсечёнными); потом старый живёт дальше под свежим номером.
- Число воркеров не решает никто в VMS: контроллер считает недостачу после переносов и пишет предложения, скрипт на хосте запускает запасные до своего потолка, запасной берёт только предложение своего набора.
- Добавили воркер — контроллер размещает на него; убрали — слот отпущен, камеры переносятся; упал — `systemd` поднимает его под тем же именем, и контроллер ничего не делает.
- Камера назначена воркеру в хранилище, а не процессу и не серверу; поэтому перезапуск не переписывает конфигурацию.

## Упражнения

1. Поставьте `TimeoutStopSec=1` и остановите воркер. Прочитайте строку слота и скажите, что сделает контроллер и сколько будут ждать камеры.
2. Камеры заказчика ночью простаивают на детекторе движения. Что покажет `vms_worker_load` ночью и почему скрипт запасных не должен ничего гасить?
3. Дайте контроллеру право запускать процессы (`systemctl start vms-vmsworker-spare@<n>` из прохода, когда `headroom()` равен нулю). Перечислите, что ему теперь нужно знать о серверах, и прогоните тест двух контроллеров.
4. В сцене `two_processes_one_name` уберите у старого процесса продление слота, оставив продление аренд эпох. Когда он остановит камеры и что окажется в архиве?
5. Контроллер «помогает»: переносит камеры истёкшего слота сразу. Перепишите сцену `a_crash_releases_nothing` и найдите момент, когда у камеры два писателя.
6. Два скрипта на `srv-b` и `srv-c` одновременно видят `vms_workers_needed{labels=""} 1`. Пройдите по шагам, что делает каждый запасной, и найдите запись, на которой второй узнаёт, что опоздал.

## Что дальше

Имена, число и три случая жизни воркера — на месте. Везде в этом уроке воркер писал своё — слот, эпохи, heartbeat — и ни разу чужое. [**Урок 5**](05-rights-by-who-is-calling.md) показывает, почему он и не может: право каждого процесса писать только свой префикс — это права сокета его роли в самом хранилище, файл прав генерируется из кода и проверяется в обе стороны, а между демонами разных серверов кто есть кто говорит сертификат.

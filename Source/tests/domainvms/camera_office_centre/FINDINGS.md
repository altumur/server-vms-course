# Находки прогона «камера, офис, центр»

Что нашёл сценарий `scenario.py` (трассы записок `_notes-ru/camera-office-centre/`), когда домен впервые работал на
configstore с закоммиченным файлом прав (`Source/deploy/cluster/configstore-rights.json`), а не на `FakeVariables`.
Код курса не правился: находка записана здесь, трасса показывает её как есть, а сценарий идёт дальше обходом, названным
в трассе строкой `##`. Пути — от `Source/`.

## Отказы прав (configstore)

### F1. Права на кластер нельзя выдать через дверь консоли домена

- Что: `PUT /domain/grants/<кластер>` и `PUT /domain/grants/domain` на консоли домена (роль `domainconsole`) падают, и
  клиент не получает ответа вовсе (соединение закрыто, `RemoteDisconnected`).
- Почему: запись идёт через `declared.guarded` (`w2cplatform/domain/console.py`, `set_grants` →
  `agent.DomainPublisher.publish_grants` / `grants.set_domain_grants`). Проверка `declared.refusal`
  (`w2cplatform/domain/declared.py`, строка с `_holds(vars_.get(family + subject))`) для строки с правом шире потолка
  семьи читает `domain/vms/stream-clients/<subject>` (семья учёток RTSP VMS, `domain.names` спеки). Роли `domainconsole`
  это чтение запрещено файлом прав (`"!domain/vms/stream-clients/*"` в её `read`). `Forbidden` обработчик не ловит —
  ответа нет.
- Когда: любая строка с `admin` или `edit` (у `view` проверки нет).
- Трасса: `03-admitted` (Анна выдаёт себе `admin` на `relay-a` и Борису `view` на домене).
- Обход в сценарии: права пишет оператор на srv через роль `domain` (`DomainPublisher.publish_grants`,
  `grants.set_domain_grants`) — как это делает команда продукта `domain grant` (`stand.sh setup`).
- Что решить: либо роль `domainconsole` читает `domain/vms/stream-clients/*` (только чтение — проверить имя), либо
  проверка имени семьи не требует её строки от того, кто пишет права; и в любом случае обработчик отвечает словами, а не
  рвёт соединение.

### F2. Дверь процессов консоли кластера `GET /api/held` падает

- Что: `GET /api/held` на консоли любого кластера (роль `console`) не отвечает (соединение закрыто).
- Почему: `term.held` (`w2cplatform/domain/term.py`) читает `domain/holder` и `domain/backup-taken`; роли `console` в
  файле прав дано чтение только `domain/keys`, `domain/member`, `domain/root`, `domain/grants`, `domain/grants/*`,
  `domain/revoked`, `domain/break_glass`.
- Следствие: агент, который следует за держателем по консолям `CLUSTERS` (`agent.HolderFollower`), не слышит ни одной
  консоли — на каждом проходе `Unreachable` от всех. Пока держатель не переезжает, это не видно: агент несёт через ту
  дверь, что у него есть. Переезд держателя агенты по `/api/held` не увидят.
- Трасса: `05-domain-learns` и каждая сцена, где проходит агент офиса после сцены 3.

### F3. Приёмник и передатчик в регистраторе не читают своих книг

- Что: на configstore регистратор офиса не поднимает передатчик вовсе: `RecWorker.host_ingest` строит
  `chain.Forwarder`, и тот в конструкторе (`restore_up` → `book`) читает `domain/vms/upstream` — `Forbidden`. Приёмник
  на каждом опросе читает `domain/vms/sources` (`ingest.should_from_snapshot`), передатчик — ещё `domain/vms/asks`
  (`Forwarder.asks_book`).
- Почему: приёмник и передатчик живут в регистраторе (ADR-0065, дополнение 2026-10-08), а роли `recworker` в файле прав
  из книг VMS дано чтение только `domain/vms/primaries`.
- Трасса: `06-office-ready` и дальше.
- Обход в сценарии: ручка приёмника и передатчика — роль `recworker` с чтением `domain/vms/sources`,
  `domain/vms/upstream`, `domain/vms/asks` сверх файла прав (накладка сценария, `stand.Site.f3_handle`); каждая её
  строка в трассе помечена дверью `/run/configstore/recworker.sock (+F3)`. Своя ручка регистратора — как в файле прав.
- Что решить: дать роли `recworker` чтение этих трёх книг (они несут токены потока — запечатаны кольцом кластера).

## Расхождения поведения (не права)

### O1. `members key` на свежем домене ничего не регистрирует

`python3 -m w2cplatform.domain.members key <член> <pub> <seal_pub>` строит `Members(vars)` без `configured`. Пока список
членов (`domain/members`) никто не записал, член из `CLUSTERS` в нём не числится, и `set_key` отвечает «not registered —
no such member». Первую запись списка в курсе делает только консоль домена (`POST /domain/members`, с `configured`) или
первая резервная копия держателя (`term._settle_members`), которой нужен живой член, — а живым члену не стать без
ключа. У продукта члены `CLUSTERS` числятся с самого начала (окно 5, `stand.sh setup`). Трасса: `03-admitted` (первая
попытка для `relay-a`); сценарий сначала принимает камеры через `POST /domain/members`, и эта запись несёт членов
`CLUSTERS` с `how: configuration`.

### O2. Стук члена недостижим, когда агент несёт через дверь

`DomainAgent._sync` выходит до отчёта, если дверь отказала (`Refused`), — а стук (`Members.knocking`) читается из отчёта.
Агент с `DOMAIN_URL` или `RELAY_URL`, которого дверь не знает, не стучит никогда, и `POST /domain/members
{name, fingerprint}` сравнить не с чем. У продукта отказанная публикация `POST /api/member/<c>` запоминается как стук
(`Members.NoteKnock`). Трассы: `02-members-knock`, `03-admitted` (`knocking: []`).

### O3. Свой отчёт офиса удаляет его сводный отчёт на каждом проходе

`uplink.report` удаляет под `domain/members/<офис>/` всё, чего нет в этом отчёте; сводный отчёт `relay.bundle` лежит там
же (`domain/members/<офис>/bundle`) и в список не входит. Каждый проход: `DELETE …/bundle`, потом `PUT …/bundle` заново —
две записи вместо нуля, и между ними у держателя нет отчёта ни одной камеры за офисом. Трасса: `05-domain-learns`.

### O4. Камера без книги держит карту и говорит, что основная запись пишется

Пока у камеры нет книги основных (`domain/vms/primaries`), толкатель не говорит ничего (`uncovered` = None), книги нет, и
`primary_needs_cover` не находит основной записи в своём кластере: `1-sd` (`when: offline`) стоит `standby`, `hold: true`,
с объяснением «the primary recording is being written». Карта не пишет, хотя камеру не пишет никто. Трасса:
`04-camera-boots`. У продукта `1-sd` без `when` (`stand.sh setup`) — карта пишет всегда.

### O5. Агент-процесс курса не несёт ни общих настроек, ни резервной копии домена

`agent.main` строит `DomainAgent` без `cluster_objects`, а шаги «the shared settings» и «the backup» в `_sync` идут только
при нём. Агент кластера, поднятый юнитом, не несёт домой подписанные общие настройки (`domain/shared`, ADR-0032) и копию
домена, которую держатель выбрал ему хранить (`domain/backup/<член>` и объект `backup/rev-N` приходят в ответе
`/api/carry`, но не берутся). Тесты передают `cluster_objects` сами. В сценарии агенты офисов собраны как `main`, агент
камеры — как его собирают тесты урока 17 (процесса камеры в курсе нет): с `console`, `current`, `seen_store`,
`cluster_objects`, `pages`, `alarm_waiting`. Держатель выбрал хранить копию `relay-b` и `cam-a` (`domain/backup/relay-b`,
`domain/backup/cam-a`, трасса `05-domain-learns`): `cam-a` её берёт (`domain/backup-taken` на флеше, `08-books-home`),
`relay-b` — нет, и `copies` держателя это видят.

### O6. Регистратор офиса не берёт поток, который камера толкает в его же приёмник

Запись `{name: SN-A, cam: ref:SN-A}` на `r-relay-a-1` стоит `waiting`, «camera held by nobody»: `RecWorker.source` ищет
камеру в heartbeat'ах VMS своего кластера, а книгу источников (`ingest://relay-a/SN-A`) и свой приёмник не спрашивает
(module-design.md М12B, открытые пункты 1 и 5). Поэтому в книге основных `running: false`, и `written_through`, по
которому приёмник отвечает камере `have`, никто не пишет. В сцене 9 подписку на приёмник делает сценарий, как тесты
урока 16 (`ingest.want` + `subscribe` от имени регистратора). Трассы: `06-office-ready`, `09-stream-flows`.

### O7. Тревоги камер за офисом не доходят до списка домена

`DomainAlarms` и у подписывающего (`signer_service.holder_pass`), и у консоли домена (`console.main`) читают страницу
тревог члена через `ReportedDoor(m, <объекты держателя>)` → `uplink.page`, то есть из `domain/members/<член>/p/alarms` в
объектах держателя. Камера за офисом отчитывается в объекты офиса, и её страница доходит до держателя только внутри
сводного отчёта (`domain/members/<офис>/bundle`), который `ReportedDoor` не читает (читает его `member_copy(..., via=…)`,
`relay.BundleView`). Итог: `GET /domain/alarms` говорит о каждой камере за офисом «has never reported to the domain»,
её тревоги в списке не появляются. Трасса: `12-alarm` (тревога `card.prebuffer.short` на cam-a2 есть на карте и в её
отчёте `p/alarms`, сводный отчёт relay-a её несёт, список домена пуст).

### O8. Член без страницы тревог «имеет больше тревог, чем страница»

Офис не отчитывается страницей тревог (агенту `main` не дают `pages`). `ReportedDoor._page` без страницы отвечает
`{"from": <сейчас>, "events": []}`, а `_cut` считает `since < from` усечением: `GET /domain/alarms` говорит «relay-a had more
alarms than one page holds; showing its newest» о члене, у которого тревог нет вовсе. Трасса: `12-alarm`.

### O9. Дверь домена отвечает за бывшего члена, если топология его ещё держит за офисом

`HolderDoor.carry(..., for_member)` для просьбы офиса проверяет только топологию (`Topology.via`), а не список членов:
после `DELETE /domain/members/cam-a2` офис `relay-a` по-прежнему получает на `?for=cam-a2` ответ 200 (публичные строки,
секреты пустые, `key: null`). Дверь офиса затем отказывает камере словами «cam-a2 was admitted without a key: it cannot
be told from anybody on the site» — о члене, которого удалили, а не «не приняли без ключа». Трасса: `f10-member-leaves`.

### O10. Камера за офисом считает свежесть книг по разговору с офисом, не с доменом

Агент камеры с `RELAY_URL` — `CarryClient` без `seen()`: отметка возраста офиса (`seen` в ответе двери офиса) читается в
`_carried_seen` и не используется (module-design.md М12B, открытый пункт 7). Пока офис отрезан от центра, камера пишет в
`domain/seen` время своего последнего разговора с офисом и считает книги свежими. Трасса: `f03-uplink`.

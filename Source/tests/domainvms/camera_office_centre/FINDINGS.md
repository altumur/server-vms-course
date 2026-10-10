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

---
genre: записки
kind: разбор кода
subject: М12B_DomainVMS
source-commit: 2cfce43c
date: 2026-10-11
status: draft
---

# Приложение. Все запросы сценария одним списком

> [!note] Записки поверх репозитория, а не его документация
> Это разбор: я читал код и восстанавливал по нему, как всё устроено, максимально простыми словами.
> **Источник истины — код.** Где записки расходятся с кодом, прав код.
> Проект описывает себя сам: [`README.md`](../../README.md) и указатели модулей.
> Состояние: коммит `2cfce43c`, 11 октября 2026.

[← карта разбора](README.md) · назад: [12-limits-and-scale.md](12-limits-and-scale.md)


Порядок — временной, по частям. Список собран из трасс [`traces/`](traces/), снятых на `main` курса `2cfce43c` без обходов: записи и сетевые запросы — из коротких трасс (`*.brief.txt`), число чтений хранилища — из полных (`*.txt`). Где трасса повторяет одно и то же подряд, здесь стоит `×N`. Ответы сокращены до существенного. Номера `index` и время условные, как везде в разборе. **Каждая сцена — свой прогон с нуля**, но прогон детерминирован: сцены до неё проигрываются без записи и оставляют те же номера. Поэтому `index` счастливого пути продолжается от сцены к сцене, а пропуски в нём — записи приглушённых проходов. Отказы начинаются из конца счастливого пути, в `1757500322`, и между собой их номера не связаны. Справа от заголовка блока — часть, где запросы разобраны.

Части 00–12 сверены с теми же трассами: номера и имена строк в них и здесь одни.

**Кто спрашивает** (первая колонка):

| Метка | Кто | Куда идут его запросы к хранилищу |
|---|---|---|
| `anna`, `boris` | люди: браузер или инструмент → консоль домена `srv:8070`, консоли кластеров `:8080` | — |
| `op-srv`, `op-ra` | оператор на коробке `srv` или `relay-a`: команда, а не дверь | роль `domain` |
| `sig` | подписывающий на `srv` (`w2c-domain`); его дверь `srv:8071`, сокет токенов | `/run/configstore/domain.sock` |
| `sig-ra` | подписывающий на `relay-a` (отказы 5 и 6) | `domain.sock` на `relay-a` |
| `dcon`, `dcon-ra` | консоль домена на `srv`, на `relay-a` | `domainconsole.sock` |
| `vmsd` | воркер VMS на домене (`vms-domainpart`) | `vmsdomain.sock`; токены — `/run/w2c-signer/tokens.sock` |
| `ag-srv`, `ag-ra`, `ag-rb`, `ag-rb2` | агент члена на сервере | `domainagent.sock` своего кластера |
| `ag-ca`, `ag-ca2`, `ag-cb` | агент камеры | флеш камеры |
| `door-ra` | дверь ретранслятора `relay-a:8446`, когда она сама идёт к двери домена | — |
| `con-srv`, `con-ra`, `con-rb`, `con-rb2` | консоль кластера | `console.sock` |
| `con-ca` | консоль камеры на её флеше | флеш |
| `rec-srv`, `rec-ra`, `rec-rb`, `rec-rb2` | регистратор с приёмником (и передатчиком у офиса) | `recworker.sock` |
| `fwd-ra`, `fwd-rb` | передатчик офиса — к приёмнику центра | — |
| `rctl-…`, `vctl-…` | контроллер записей и контроллер VMS кластера | `reccontroller.sock`, `vmscontroller.sock` |
| `card-ca`, `card-ca2` | регистратор карты `r-1` на камере | флеш |
| `cam-ca` | камера при загрузке (`DeviceCluster.boot`) | флеш |
| `push-ca`, `push-cb` | толкатель камеры | читает флеш |
| `ask-ca2`, `auto-ca2` | сценарий на камере `cam-a2` | флеш |
| `gw` | шлюз зрителя в центре (модель курса) | `console.sock` на `srv` |
| `res-…` | ресурс сервера | `resource.sock` |

**Как читать строку.**

- `put <ключ> cas=…  → index N` — запись в хранилище `configstore` (у камеры — на флеш). `cas=""` — только создать, `cas=N` — только если версия ещё `N`, `cas=null` — безусловно. `delete` — удаление.
- `GET /api/…`, `/domain/…`, `/rec/…` — настоящий HTTP курса. `→ 0 «no answer: …»` — коробка выключена или дорога перерезана.
- `PUT /domain/members/<член>/…` — отчёт члена в чужие объекты: у курса это вызов в процессе, у продукта — `POST /api/member/<член>`. Пути под `o/` — объекты кластера, `v/` — строки его хранилища, `p/alarms` — страница тревог.
- `GET /ingest/<ref>/poll`, `POST /ingest/<ref>/live`, `…/ask`, `…/answer/<id>`, `RTSP` — вызовы приёмника в процессе, напечатанные маршрутами продукта.
- `carry 200: a, b, c` — какие строки дверь отдала (без `domain/` и без хвоста `/<член>`); `+obj` — какие объекты.
- `чтения:` — сколько чтений хранилища (`GET /v1/get`, `GET /v1/list`) сделал каждый процесс в этом блоке; по одной они не перечислены.

```
── 2 сцена 1: домен основан на srv ─────────────────────────────────────────────────────────────────── (2)
sig       put domain/signer cas=""                       → index 1002   первый старт с RECOVERY_FILE: ключи выданы корнем
sig       put domain/keys cas=""                         → index 1003   набор rev 1, подписан корнем
sig       put domain/holder cas=""                       → index 1004   срок 1, srv, kid root
op-srv    put domain/users/anna cas=""                   → index 1005   хеш пароля запечатан
op-srv    put domain/grants/domain cas=""                → index 1006   anna|admin|, 0.0
vmsd      GET /kinds                                     → 200 stream, ask
ag-srv    put domain/member-key cas=""                   → index 1007
          первый проход подписывающего: объекты держателя через ресурс srv
sig       GET /v1/objects/domain/members/relay-a/reported?scope=cluster  → 404   ×5
sig       GET /v1/objects/domain/members/relay-b/reported?scope=cluster  → 404   ×5
sig       GET /v1/objects?prefix=vms/heartbeats/&scope=cluster          → 200 пусто
sig       GET /v1/objects?prefix=vms/snapshot/&scope=cluster            → 200 пусто ×3
sig       GET /v1/objects?prefix=domain/members/&scope=cluster          → 200 пусто
sig       GET /v1/objects?prefix=domain/knocks/&scope=cluster           → 200 пусто
sig       FILE domain/view
          первый проход воркера VMS на домене
vmsd      put domain/vms/worker cas=""                   → index 1008   слот прохода
vmsd      put domain/vms/stream-accounts/relay-a cas=""  → index 1009   пустой список учёток
vmsd      put domain/vms/stream-accounts/relay-b cas=""  → index 1010
vmsd      put domain/vms/stream-accounts/srv cas=""      → index 1011
          первый проход агента держателя: своё хранилище, без двери
ag-srv    put domain/root cas=null                       → index 1012   закреплён корень
ag-srv    put domain/vms/stream-accounts cas=""          → index 1013
ag-srv    put domain/member cas=""                       → index 1014
          чтения: ag-srv 38, sig 37, vmsd 23, op-srv 6, con-srv 2, res-srv 1 — 107; объектов 16

── 3 сцена 2: члены стучатся ──────────────────────────────────────────────────────────────────────── (3)
ag-ra     put domain/member-key cas=""                   → index 2002   печатает отпечаток aed1094b512882d3
ag-rb     put domain/member-key cas=""                   → index 3002   dfa7249860ac38de
ag-ra     GET /api/carry/relay-a → srv:8071              → 403 «relay-a is no member with a key: …»
ag-ca     put domain/member-key cas=0                    → index 4001   ded5c4163c5ea70b
ag-ca2    put domain/member-key cas=0                    → index 5001   f1e06c0a38bde236
ag-cb     put domain/member-key cas=0                    → index 6001   2538c5332af11dfd
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 403 «cam-a is no member with a key: …»
door-ra   GET /api/carry/cam-a → srv:8071                → 403 то же; дверь офиса несёт стук камеры держателю
vmsd      put domain/vms/worker cas=1008                 → index 1015
          чтения: vmsd 23, sig 21, ag-ra 4, остальные по 2 — 64

── 3 сцена 3: приём, топология, права ─────────────────────────────────────────────────────────────── (3)
op-srv    put domain/members cas=""                      → index 1016   members key relay-a: первая запись списка
op-srv    put domain/members cas=1016                    → index 1017   members key relay-b
anna      POST /api/login → srv:8070                     → 200 «токен 1: person sub=anna на 900 с»
dcon      POST /api/login → srv:8071  X-Operator: domain-console  → 200 тот же токен
anna      GET /domain/members                            → 200 rev, members, pinned, knocking: cam-a, cam-a2, cam-b
anna      POST /domain/members {cam-a, fingerprint ded5c4163c5ea70b}   → 200
dcon      GET /api/holder                                → 200 срок 1, deposed false
dcon      put domain/members cas=1017                    → index 1018
          …то же для cam-a2 (1019) и cam-b (1020): по GET /api/holder перед каждой записью
anna      GET /domain/topology, PUT /domain/topology     → 200 rev 1
dcon      GET /api/holder; put domain/topology cas=""    → index 1021   центр srv, via: камеры через свои офисы
anna      PUT /domain/grants/srv {anna admin *}          → 200
dcon      GET /api/holder; put domain/grants/srv cas=""  → index 1022
          …relay-a (1023), relay-b (1024)
anna      POST /domain/users {boris}                     → 200
dcon      GET /api/holder; POST /api/people/users → srv:8071  → 200
sig       put domain/users/boris cas=""                  → index 1025
anna      PUT /domain/grants/domain                      → 200
dcon      GET /api/holder; put domain/grants/domain cas=1006  → index 1026   + boris|view|
          проход держателя
sig       put identity/pointer cas=""                    → index 1027   identity/rev-1
vmsd      put domain/vms/worker cas=1015                 → index 1028
vmsd      put domain/vms/stream-accounts/cam-a, cam-a2, cam-b cas=""  → index 1029–1031
          проход агента relay-a
ag-ra     GET /api/carry/relay-a → srv:8071              → 200 keys, holder, topology, members, grants, stream-accounts
ag-ra     put domain/root cas=null                       → index 2003
ag-ra     put domain/keys, grants, topology, member-list, vms/stream-accounts, member, holder cas=""  → index 2004–2010
ag-ra     GET /api/carry/relay-a?for=cam-a               → 200 keys, holder, topology, members, stream-accounts
ag-ra     GET /api/carry/relay-a?for=cam-a2              → 200 то же
ag-ra     PUT /domain/members/relay-a/bundle             → 200 {}
          проход агента cam-a
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 то же + seen age 0.0
ag-ca     put domain/root cas=""                         → index 4002
ag-ca     put domain/keys, topology, member-list, vms/stream-accounts, member, holder cas=0  → index 4003–4008
          чтения: sig 116, dcon 76, vmsd 44, ag-ra 23, ag-ca 21, op-srv 6 и другие — 288

── 4 сцена 4: камера cam-a загружается ────────────────────────────────────────────────────────────── (4)
cam-ca    put vms/epoch/1 cas=0                          → index 4009   эпоха 1
cam-ca    put vms/cameras/1 cas=0                        → index 4010   ref SN-A, первая загрузка
cam-ca    put rec/volumes/card cas=0                     → index 4011   карта — том, kind edge
con-ca    put rec/recordings/1-sd cas=0                  → index 4012   home card, when offline
card-ca   put rec/slots/r-1 cas=0                        → index 4013
card-ca   put rec/slots/r-1 cas=4013                     → index 4014
card-ca   put rec/holds/card cas=0                       → index 4015
rctl-ca   put rec/placement/1-sd cas=0                   → index 4016
rctl-ca   put rec/workers/r-1 cas=0                      → index 4017
card-ca   put rec/epoch/1-sd cas=0                       → index 4018
          пять секунд: кольцо, толкатель без книг, карта standby
          чтения: card-ca 59, rctl-ca 24, push-ca 10, cam-ca 7, con-ca 3 — 103

── 4 сцена 5: домен узнаёт камеры ─────────────────────────────────────────────────────────────────── (4)
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 keys, holder, topology, members, stream-accounts
ag-ca     PUT /domain/members/cam-a/o/rec/heartbeats/r-1, o/vms/heartbeats/SN-A, o/vms/snapshot/SN-A,
              o/domain/reaches                           → 200        в объекты relay-a
ag-ca     PUT /domain/members/cam-a/v/domain/holder, v/domain/root, v/domain/keys,
              v/rec/epoch/1-sd, v/vms/epoch/1            → 200
ag-ca     PUT /domain/members/cam-a/p/alarms             → 200 events []
ag-ca     PUT /domain/members/cam-a/reported             → 200 seq, items, key, seal
ag-ra     GET /api/held → relay-a:8080, relay-b:8080, srv:8080  → 200 срок 1 srv
ag-ra     GET /api/carry/relay-a                         → 200 keys, holder, topology, members, grants, stream-accounts
ag-ra     PUT /domain/members/relay-a/o/rec/snapshot/unplaced, o/vms/snapshot/unplaced, o/domain/reaches,
              v/domain/holder, v/domain/root, v/domain/keys, reported   → 200    в объекты srv
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2  → 200
ag-ra     PUT /domain/members/relay-a/bundle             → 200 {cam-a, cam-a2}
sig       put domain/keepers/relay-b cas=""              → index 1035   первая копия домена
sig       put domain/keepers/cam-a cas=""                → index 1036
vmsd      put domain/vms/worker cas=1028                 → index 1037
anna      POST /api/login                                → 200 «токен 1»   (dcon → srv:8071 /api/login)
anna      GET /domain/vms/cameras                        → 200 rows, clusters, why
anna      GET /domain/where/SN-A                         → 200 unit, worker, server, cluster, searched, unreachable
          чтения: sig 114, vmsd 59, ag-ra 38, ag-ca 36, dcon 13, контроллеры офисов 46 и другие — 318

── 5 сцена 6: офис готов писать ───────────────────────────────────────────────────────────────────── (5)
anna      POST /api/login                                → 200 «токен 1»   (dcon → srv:8071)
anna      POST /rec/volumes → relay-a:8080               → 201
con-ra    put rec/volumes/disk cas=""                    → index 2011
rec-ra    put rec/slots/r-relay-a-1 cas=""               → index 2012   регистратор с приёмником и передатчиком
anna      POST /rec/recordings {SN-A, cam ref:SN-A} → relay-a:8080  → 201
con-ra    put rec/idem/relay-a-SN-A cas=""               → index 2013
con-ra    put rec/idem/relay-a-SN-A cas=2013             → index 2014
con-ra    put rec/recordings/SN-A cas=""                 → index 2015
con-ra    put rec/idem/relay-a-SN-A cas=2014             → index 2016
rec-ra    put rec/slots/r-relay-a-1 cas=2012             → index 2017
rec-ra    put rec/holds/disk cas=""                      → index 2018
rec-ra    put rec/holds/disk cas=2018, cas=2019          → index 2019, 2021
rec-ra    put objects/rec/used/disk cas=null             → index 2020
rctl-ra   put rec/placement/SN-A cas=""                  → index 2022
rctl-ra   put rec/workers/r-relay-a-1 cas=""             → index 2023
rec-ra    put rec/epoch/SN-A cas=""                      → index 2024
          чтения: rec-ra 30, rctl-ra 21, con-ra 19, vctl-ra 12 и другие — 88

── 6 сцена 7: кто пишет SN-A ──────────────────────────────────────────────────────────────────────── (6)
vmsd      put domain/vms/crossings cas=""                → index 1042   SN-A → relay-a (Crossings.record; у продукта
                                                                        POST /domain/vms/crossings)
vmsd      put domain/vms/worker cas=1037                 → index 1044
vmsd      put domain/vms/sources/relay-a cas=""          → index 1045
vmsd      put domain/vms/sources/relay-b cas=""          → index 1046
vmsd      POST /tokens/stream {sub cam-a, aud ingest:relay-a, ref SN-A}   → 200 «токен 1 … на 86400 с»
vmsd      POST /tokens/stream {sub cam-b, aud ingest:relay-b, ref SN-B}   → 200 «токен 2»
vmsd      put domain/vms/primaries/cam-a cas=""          → index 1047
vmsd      put domain/vms/primaries/cam-b cas=""          → index 1048
vmsd      POST /tokens/stream {sub cam-a2, aud ingest:relay-a, ref SN-A2} → 200 «токен 3»
vmsd      put domain/vms/polls/cam-a2 cas=""             → index 1049
vmsd      POST /tokens/stream {sub relay-a, aud ingest:srv, ref SN-A}     → 200 «токен 4»
vmsd      POST /tokens/stream {sub relay-b, aud ingest:srv, ref SN-B}     → 200 «токен 5»
vmsd      POST /tokens/stream {sub relay-a, aud ingest:srv, ref SN-A2}    → 200 «токен 6»
vmsd      put domain/vms/upstream/relay-a cas=""         → index 1050
vmsd      put domain/vms/upstream/relay-b cas=""         → index 1051
          чтения: vmsd 66, контроллеры офисов 10 — 76

── 6 сцена 8: книги уходят домой ──────────────────────────────────────────────────────────────────── (6)
ag-ra     GET /api/held ×3                               → 200 срок 1 srv; relay-b хранит копию rev 1
ag-ra     GET /api/carry/relay-a                         → 200 keys, holder, topology, members, grants, sources,
                                                                stream-accounts, upstream
ag-ra     put domain/vms/sources cas=""                  → index 2025
ag-ra     put domain/vms/upstream cas=""                 → index 2026   токены перезапечатаны кольцом relay-a
ag-ra     PUT /domain/members/relay-a/reported           → 200
ag-ra     GET /api/carry/relay-a?for=cam-a               → 200 … keepers, primaries … +backup/rev-2
ag-ra     GET /api/carry/relay-a?for=cam-a2              → 200 … polls …
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 … keepers, primaries … +backup/rev-2, seen age 0.0
ag-ca     put domain/vms/primaries cas=0                 → index 4020
ag-ca     put domain/backup-taken cas=4019               → index 4021
ag-ca     PUT /domain/members/cam-a/v/domain/backup-taken, p/alarms, reported  → 200
          чтения: sig 56, ag-ra 39, ag-ca 37 и другие — 153

── 7 сцена 9: поток пошёл ─────────────────────────────────────────────────────────────────────────── (7)
rec-ra    put rec/slots/r-relay-a-1 cas=2017             → index 2027
rec-ra    put rec/holds/disk cas=2021, cas=2028          → index 2028, 2029
rec-ra    put rec/epoch/SN-A cas=2024                    → index 2030   запись берёт SN-A из книги источников
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true
rec-ra    put objects/rec/ingest/clock/SN-A.json cas=null  → index 2031  перевод часов камеры
push-ca   POST /ingest/SN-A/live                         → 200 611     кольцо целиком
rec-ra    put rec/slots/r-relay-a-1, rec/holds/disk ×2   → index 2032–2034
push-ca   GET /ingest/SN-A/poll                          → 200 push true, have 1757500261
push-ca   POST /ingest/SN-A/live                         → 200 10
rec-ra    put rec/slots/r-relay-a-1, rec/holds/disk ×2   → index 2035–2037
push-ca   GET /ingest/SN-A/poll                          → 200 push true, have 1757500262
push-ca   POST /ingest/SN-A/live                         → 200 10
rec-ra    put rec/slots/r-relay-a-1, rec/holds/disk ×2   → index 2038–2040
rec-ra    FILE rec/heartbeats/r-relay-a-1, rec/polled/http___relay-a_8091_ingest
          чтения: rec-ra 89, card-ca 16, контроллеры офисов 40 и другие — 149

── 8 сцена 10: Борис смотрит из центра ────────────────────────────────────────────────────────────── (8)
boris     POST /api/login                                → 200 «токен 1: person sub=boris на 900 с»
gw        RTSP rtsp://…/ingest/SN-A {who gw-centre} → srv:8091  → 200
fwd-ra    GET /ingest/SN-A/poll → srv:8091               → 200 push true
rec-ra    put objects/rec/ingest/up/SN-A.json cas=null   → index 2041   слово центра
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
rec-ra    delete objects/rec/ingest/up/SN-A2.json        → index 2042
push-ca   GET /ingest/SN-A/poll                          → 200 push true, have 1757500263
push-ca   POST /ingest/SN-A/live                         → 200 60
fwd-ra    GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 push true; 200 60
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
push-ca   GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200; 200 10
fwd-ra    GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 push true; 200 10
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
          Борис получил 30 кадров; ушёл; LINGER 10 с
push-ca   GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200; 200 110
fwd-ra    GET /ingest/SN-A/poll                          → 200 push false   центр больше не хочет
rec-ra    delete objects/rec/ingest/up/SN-A.json         → index 2043
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
          чтения: rec-ra 19, rec-srv 18, card-ca 14, контроллеры офисов 40 и другие — 104

── 9 сцена 11: сценарий между объектами ───────────────────────────────────────────────────────────── (9)
anna      POST /api/login                                → 200 «токен 1»
anna      GET /domain/shared                             → 200 doc, delivery, declared
anna      PUT /domain/shared {auto: scenarios}           → 200 rev, by
dcon      GET /api/holder; PUT /api/shared → srv:8071    → 200 rev, by
sig       put domain/shared cas=""                       → index 1053   shared/rev-1, подписан
sig       put domain/keepers/relay-b cas=1040            → index 1054   копия rev 3
sig       put domain/keepers/cam-a cas=1041              → index 1055
vmsd      put domain/vms/worker cas=1044                 → index 1056
vmsd      GET /kid ×6                                    → 200 fc357029
vmsd      POST /tokens/ask                               → 200 «токен 2: ask sub=cam-a2 aud=ingest:relay-a ref=SN-B»
vmsd      POST /tokens/ask                               → 200 «токен 3: ask sub=relay-a aud=ingest:srv ref=SN-B»
vmsd      put domain/vms/asks/relay-a cas=""             → index 1057
vmsd      put domain/vms/asks/cam-a2 cas=""              → index 1058
ag-ra     GET /api/held ×3                               → 200 срок 1 srv; relay-b хранит копию rev 2
ag-ra     GET /api/carry/relay-a                         → 200 keys, holder, shared, topology, members, grants, asks,
                                                                sources, stream-accounts, upstream +shared/rev-1
ag-ra     put domain/vms/asks cas=""                     → index 2044
ag-ra     put domain/shared cas=""                       → index 2045
ag-ra     PUT /domain/members/relay-a/o/rec/heartbeats/r-relay-a-1, o/rec/polled/…, v/domain/shared,
              v/rec/epoch/SN-A, reported                 → 200
ag-ra     GET /api/carry/relay-a?for=cam-a               → 200 … +shared/rev-1, backup/rev-3
ag-ra     GET /api/carry/relay-a?for=cam-a2              → 200 … asks, polls …
ag-ra     PUT /domain/members/relay-a/bundle             → 200
ag-ca2    GET /api/carry/cam-a2 → relay-a:8446           → 200 … asks, polls … +shared/rev-1
ag-ca2    put domain/vms/asks cas=0                      → index 5020
ag-ca2    put domain/shared cas=0                        → index 5021
ag-ca2    PUT /domain/members/cam-a2/v/domain/shared, p/alarms, reported  → 200
          событие на cam-a2: машина
ask-ca2   POST /ingest/SN-B/ask → relay-a:8091           → 200 cacab392
fwd-ra    POST /ingest/SN-B/ask → srv:8091               → 200 35b0be3a
fwd-ra    GET /ingest/SN-B/ask/35b0be3a                  → 200
fwd-rb    GET /ingest/SN-B/poll → srv:8091               → 200 push false, asks 1
rec-rb    delete objects/rec/ingest/up/SN-B.json         → index 3031
push-cb   GET /ingest/SN-B/poll → relay-b:8091           → 200 push false, asks 1
rec-rb    put objects/rec/ingest/clock/SN-B.json cas=null  → index 3032
push-cb   POST /ingest/SN-B/answer/35b0be3a              → 200   preset 3 performed
fwd-rb    POST /ingest/SN-B/answer/35b0be3a → srv:8091   → 200
fwd-ra    GET /ingest/SN-B/ask/35b0be3a → srv:8091       → 200 performed
ask-ca2   GET /ingest/SN-B/ask/cacab392 → relay-a:8091   → 200 performed
          чтения: sig 123, vmsd 77, ag-ra 40, ag-ca2 37 и другие — 337

── 9 сцена 12: тревога с камеры ───────────────────────────────────────────────────────────────────── (9)
          card-ca2: prebuffer_pass → card.prebuffer.short на карте; агент отчитывается сразу (report_now)
ag-ca2    GET /api/carry/cam-a2 → relay-a:8446           → 200
ag-ca2    PUT /domain/members/cam-a2/o/rec/heartbeats/r-1, o/vms/heartbeats/SN-A2, o/vms/snapshot/SN-A2,
              p/alarms, reported                         → 200        в p/alarms — тревога
ag-ra     GET /api/held ×3                               → 200 срок 1 srv; relay-b хранит копию rev 3
ag-ra     GET /api/carry/relay-a                         → 200
ag-ra     PUT /domain/members/relay-a/reported           → 200
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2  → 200
ag-ra     PUT /domain/members/relay-a/bundle             → 200 {cam-a, cam-a2}
sig       put domain/keepers/relay-b cas=1054            → index 1060   копия rev 4
sig       put domain/keepers/cam-a cas=1055              → index 1061
anna      POST /api/login                                → 200 «токен 1»
anna      GET /domain/alarms                             → 200 events, members, complete, sentence
          чтения: sig 116, ag-ra 40, ag-ca2 37, dcon 10 и другие — 225
```

## Отказы части 10

В счастливом пути этих запросов нет. Каждый блок — свой прогон, начатый из конца сцены 12 в `1757500322`. Свёрнутые минуты и часы (`## … (свёрнуто)` в трассе) здесь отмечены строкой без метки.

```
── 10.1 офис relay-a выключен на 5 минут ──────────────────────────────────────────────────────── (10.1)
anna      POST /api/login                                → 200 «токен 1»
          relay-a выключен; шаг камеры в 323: «no ingest of relay-a answered»
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 0 «no answer: relay-a is off»
          60 с свёрнуто; карта: 13 сегментов, 317 352 Б
anna      GET /domain/vms/cameras                        → 200 relay-a, cam-a, cam-a2 unreachable
                                                                «has not reported for 66 s», complete false
          ещё 4 мин свёрнуто; карта: 37 сегментов, 946 272 Б
          relay-a включён; шаг камеры в 624
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true, have 1757500281
push-ca   POST /ingest/SN-A/live                         → 200 301     594.0…624.0; left_s 313
ag-ra     GET /api/held ×3                               → 200 срок 1 srv; relay-b хранит копию rev 13
ag-ra     GET /api/carry/relay-a                         → 200 keys, holder, shared, topology, members, grants, asks,
                                                                sources, stream-accounts, upstream
ag-ra     put domain/vms/asks cas=2044                   → index 2047
ag-ra     put domain/vms/sources cas=2025                → index 2048   SN-A reachable false, as_of 323
ag-ra     PUT /domain/members/relay-a/o/rec/heartbeats/r-relay-a-1, o/rec/polled/…, reported  → 200   seq 9
ag-ra     GET /api/carry/relay-a?for=cam-a               → 200 … +backup/rev-5
ag-ra     GET /api/carry/relay-a?for=cam-a2              → 200
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 … seen age 0.0
ag-ca     put domain/vms/primaries cas=4020              → index 4024   recording "", running false
ag-ca     put domain/backup-taken cas=4023               → index 4025   rev 5
ag-ca     PUT /domain/members/cam-a/o/rec/heartbeats/r-1, o/vms/heartbeats/SN-A, o/vms/snapshot/SN-A,
              v/domain/backup-taken, p/alarms, reported  → 200   seq 5
          30 с свёрнуто; карта: 40 сегментов, owed_s 312.9, owed_gaps 1
anna      GET /domain/vms/cameras                        → 200 все ok, complete true
          чтения: sig 129, ag-ra 40, ag-ca 38, dcon 20, card-ca 16 и другие — 295

── 10.2 обрыв cam-a — relay-a: минута и полчаса ───────────────────────────────────────────────── (10.2)
anna      POST /api/login                                → 200 «токен 1»
          дорога перерезана; шаг в 323: «no ingest of relay-a answered»; 59 с свёрнуто
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true, have 1757500281
push-ca   POST /ingest/SN-A/live                         → 200 291     354.0…383.0; left_s 72
          20 с свёрнуто; карта: 15 сегментов, owed_s 72.9, owed_gaps 1
          дорога перерезана снова; 1800 с свёрнуто; карта: 195 сегментов, 5 086 662 Б
push-ca   GET /ingest/SN-A/poll                          → 200 push true, have 1757500403
push-ca   POST /ingest/SN-A/live                         → 200 301     2174.0…2204.0; left_s 1843
          30 с свёрнуто; карта: 198 сегментов, owed_s 1843.8, owed_gaps 2
          записей нет; чтения: card-ca 22, контроллеры офисов 40, rec-ra 6 и другие — 79

── 10.3 обрыв relay-a — srv ───────────────────────────────────────────────────────────────────── (10.3)
boris     POST /api/login                                → 200 «токен 1: person sub=boris»
gw        RTSP rtsp://…/ingest/SN-A → srv:8091           → 200
          10 с свёрнуто: Борис получил 30 кадров; дорога relay-a — srv перерезана
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true, have 1757500332
push-ca   POST /ingest/SN-A/live                         → 200 10
ag-ra     GET /api/held → relay-a:8080, relay-b:8080     → 200 срок 1 srv; relay-b хранит копию rev 4
ag-ra     GET /api/held → srv:8080                       → 0 «no answer: the road relay-a — srv is cut»
ag-ra     GET /api/carry/relay-a → srv:8071              → 0 то же
          30 с свёрнуто: Борис получил 0 кадров; written_through 363
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 … +backup/rev-4, seen n 16, age 31.0
ag-ca     PUT /domain/members/cam-a/o/vms/heartbeats/SN-A, o/vms/snapshot/SN-A, p/alarms, reported  → 200  seq 7
          domain/seen в RAM камеры: ts 1757500332; дорога вернулась
push-ca   GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 have 1757500363; 200 10
fwd-ra    GET /ingest/SN-A/poll → srv:8091               → 200 push true
fwd-ra    POST /ingest/SN-A/live                         → 200 300     334.1…364.0; 290 отброшено
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
          Борис получил 30 кадров
          записей нет; чтения: ag-ca 38, rec-ra 12 и другие — 109

── 10.4 центр srv выключен на 6 часов ─────────────────────────────────────────────────────────── (10.4)
anna      POST /api/login                                → 200 «токен 1»
          токен потока cam-a до 1757586645 — ещё 86 323 с; srv выключен
anna      GET /domain/vms/cameras → srv:8070             → 0 «no answer: srv is off»
ag-ra     GET /api/held → relay-a:8080, relay-b:8080     → 200 срок 1 srv; relay-b хранит копию rev 3
ag-ra     GET /api/held → srv:8080                       → 0 «no answer: srv is off»
ag-ra     GET /api/carry/relay-a → srv:8071              → 0 то же
          6 ч свёрнуто
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true, have 1757521922
push-ca   POST /ingest/SN-A/live                         → 200 10      токен прежний, ещё 64 722 с
          srv включён
vmsd      put domain/vms/worker cas=1056                 → index 1062
vmsd      put domain/vms/sources/relay-a cas=1045        → index 1063   reachable true
vmsd      put domain/vms/sources/relay-b cas=1046        → index 1064
vmsd      GET /kid ×2                                    → 200 fc357029   токен не перевыпущен
vmsd      put domain/vms/primaries/cam-a cas=1047        → index 1065   running true, until прежний
vmsd      GET /kid ×4                                    → 200 fc357029
vmsd      put domain/vms/asks/cam-a2 cas=1058            → index 1066
vmsd      put domain/vms/asks/relay-a cas=1057           → index 1067
ag-ra     GET /api/held ×3                               → 200 срок 1 srv
ag-ra     GET /api/carry/relay-a                         → 200
ag-ra     put domain/vms/asks cas=2044                   → index 3127
ag-ra     put domain/vms/sources cas=2025                → index 3128
ag-ra     PUT /domain/members/relay-a/o/rec/heartbeats/…, o/rec/polled/…, reported  → 200
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2  → 200
ag-ra     PUT /domain/members/relay-a/bundle             → 200
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200 … seen age 0.0
ag-ca     put domain/vms/primaries cas=4020              → index 4024
ag-ca     put domain/backup-taken cas=4023               → index 4025
ag-ca     PUT /domain/members/cam-a/o/…×3, v/domain/backup-taken, p/alarms, reported  → 200   seq 77
sig       put domain/keepers/cam-a cas=1061              → index 1068   копия rev 5
sig       put domain/keepers/relay-a cas=""              → index 1069   relay-b молчит — хранит relay-a
vmsd      put domain/vms/worker cas=1062                 → index 1070
vmsd      put domain/vms/sources/relay-a cas=1063        → index 1071
vmsd      GET /kid ×6                                    → 200 fc357029
anna      POST /api/login                                → 200 «токен 3»
anna      GET /domain/vms/cameras                        → 200 relay-b, cam-b «has not reported for 21606 s»
          чтения: vmsd 154, sig 153, ag-ra 43, ag-ca 38, dcon 17 и другие — 452

── 10.5 держатель перенесён на relay-a ────────────────────────────────────────────────────────── (10.5)
          srv выключен навсегда; на relay-a стартуют подписывающий и консоль домена
sig-ra    put domain/signer cas=""                       → index 2047   свои ключи, kid 00da92aa, без issued
op-ra     POST /domain/move {recovery, stolen false} → relay-a:8070   → …
dcon-ra   POST /api/move → relay-a:8071                  → …
sig-ra    GET /api/held → srv:8080                       → 0 «no answer: srv is off»
sig-ra    GET /api/held → relay-b:8080                   → 200 срок 1 srv, копия term 1 rev 3
sig-ra    GET /api/held → srv:8080                       → 0 то же
sig-ra    put domain/signer cas=2047                     → index 2048   выданы корнем: issued true, kid 83f49668
sig-ra    GET /api/held → srv:8080                       → 0 то же
sig-ra    GET /api/backup → relay-b:8080  X-W2C-Time, X-W2C-Signature  → 200 pointer rev 3, backup, shared
sig-ra    put domain/grants/domain, /relay-a, /relay-b, /srv cas=""      → index 2049–2052
sig-ra    put domain/members cas=""                      → index 2053   rev 5
sig-ra    put domain/shared cas=2045                     → index 2054   term 1
sig-ra    put domain/topology cas=2006                   → index 2055
sig-ra    put domain/users/anna, domain/users/boris cas=""  → index 2056, 2057
sig-ra    put domain/vms/crossings cas=""                → index 2058   SN-A relay-a, SN-B relay-b
sig-ra    put domain/members cas=2053                    → index 2059   rev 6: + srv «held the domain until term 1»
sig-ra    put domain/keys cas=2004                       → index 2060   current 83f49668; fc357029 до 1757503922
sig-ra    put domain/shared cas=2054                     → index 2061   shared/rev-1-term-2
sig-ra    put domain/holder cas=2010                     → index 2062   срок 2, relay-a, url http://relay-a:8071
sig-ra    put domain/revoked cas=""                      → index 2063
dcon-ra   ← 200 term 2, rev 3, restored_from relay-b; op-ra ← то же
ag-rb     GET /api/held → relay-a:8080                   → 200 срок 2 relay-a, url relay-a:8071
ag-rb     GET /api/held → relay-b:8080                   → 200 срок 1 srv, копия rev 3
ag-rb     GET /api/held → srv:8080                       → 0 «no answer: srv is off»
ag-rb     put domain/holder cas=3010                     → index 3033   срок 2
ag-rb     GET /api/carry/relay-b → relay-a:8071          → 200 keys, revoked, holder, shared, topology, members,
                                                                grants +shared/rev-1-term-2
ag-rb     put domain/keys cas=3004                       → index 3034
ag-rb     put domain/revoked cas=""                      → index 3035
ag-rb     put domain/member-list cas=3007                → index 3036
ag-rb     put domain/shared cas=3029                     → index 3037
ag-rb     GET /domain/members/relay-b/o/rec/heartbeats/r-relay-b-1 → объекты srv  → 0 «no answer: srv is off»   N5
ag-ra     GET /api/held → relay-a:8080, relay-b:8080     → 200 срок 2 relay-a
ag-ra     GET /api/held → srv:8080                       → 0 то же
ag-ra     GET /api/carry/relay-a → relay-a:8071          → 200 keys, revoked, holder, shared, topology, members, grants
ag-ra     put domain/member-list cas=2007                → index 2064
ag-ra     GET /domain/members/relay-a/o/rec/heartbeats/r-relay-a-1 → объекты srv  → 0 то же   N5; ?for= нет
          чтения: sig-ra 94, ag-rb 39, ag-ra 38, con-rb 11 и другие — 210

── 10.6 старый держатель srv вернулся ─────────────────────────────────────────────────────────── (10.6)
          отказ 5 проигран без записи; через 60 с srv включён
          проход sig: записей нет
op-srv    GET /api/holder → srv:8071                     → 200 срок 1, deposed false
ag-ra     GET /api/held → relay-a:8080, relay-b:8080     → 200 срок 2 relay-a
ag-ra     GET /api/held → srv:8080                       → 200 срок 1 srv    меньший срок не берётся
ag-ra     GET /api/carry/relay-a → relay-a:8071          → 200
ag-ra     PUT /domain/members/relay-a/v/domain/shared, v/domain/holder (срок 2), v/domain/keys, reported
                                                         → 200        в объекты srv: N5
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2 → relay-a:8071  → 200
sig       put domain/stranded cas=null                   → index 1062   base rev 3, holder relay-a, items []
sig       put domain/signer cas=1002                     → index 1063   forgotten: deposed by term 2
op-srv    GET /api/holder → srv:8071                     → 200 deposed true, deposed_by срок 2 relay-a, stranded []
ag-rb     GET /api/held ×3                               → 200 срок 2 relay-a; srv:8080 — срок 1
ag-rb     GET /api/carry/relay-b → relay-a:8071          → 200
ag-rb     PUT /domain/members/relay-b/v/domain/shared, v/domain/holder, v/domain/keys, reported  → 200  объекты srv
ag-rb     GET /api/carry/relay-b?for=cam-b → relay-a:8071  → 200
          чтения: sig 98, sig-ra 93, ag-ra 40, ag-rb 40 и другие — 302

── 10.7 камера cam-a перезагрузилась ──────────────────────────────────────────────────────────── (10.7)
cam-ca    GET platform/epoch_floor → пусто; GET vms/epoch/1 → 1 @4009
cam-ca    put vms/epoch/1 cas=4009                       → index 4024   эпоха 2
card-ca   put rec/slots/r-1 cas=4014                     → index 4025   holder cam-a:4103:001007, gen 2
card-ca   put rec/slots/r-1 cas=4025                     → index 4026
card-ca   put rec/holds/card cas=4015                    → index 4027
card-ca   put rec/epoch/1-sd cas=4018                    → index 4028   эпоха 2
push-ca   GET /ingest/SN-A/poll {version -1} → relay-a:8091  → 200 push true, have 1757500281
push-ca   POST /ingest/SN-A/live                         → 200 11      322.0…323.0, новое кольцо
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200
ag-ca     PUT /domain/members/cam-a/o/rec/heartbeats/r-1, o/vms/heartbeats/SN-A (cam-a-boot-2),
              o/vms/snapshot/SN-A, v/rec/epoch/1-sd, v/vms/epoch/1, p/alarms, reported  → 200   seq 5
ag-ra     GET /api/held ×3; GET /api/carry/relay-a       → 200
ag-ra     PUT /domain/members/relay-a/reported           → 200
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2  → 200
ag-ra     PUT /domain/members/relay-a/bundle             → 200
vmsd      put domain/vms/worker cas=1056                 → index 1062
vmsd      put domain/vms/sources/relay-a, /relay-b       → index 1063, 1064
vmsd      GET /kid ×2; put domain/vms/primaries/cam-a cas=1047  → index 1065
vmsd      GET /kid ×4; put domain/vms/asks/cam-a2, /relay-a      → index 1066, 1067
anna      POST /api/login                                → 200 «токен 2»
anna      GET /domain/vms/cameras                        → 200 SN-A epoch 2, live, age 0; complete true
          чтения: sig 91, vmsd 77, ag-ra 40, ag-ca 38, card-ca 33 и другие — 329

── 10.8 регистратор центра перезапустился ─────────────────────────────────────────────────────── (10.8)
boris     POST /api/login                                → 200 «токен 1»
gw        RTSP rtsp://…/ingest/SN-A → srv:8091           → 200
          10 с свёрнуто; r-srv-1 перезапущен
rec-srv   GET platform/schema, platform/decommission/srv, list rec/slots/, rec/slots/r-srv-1 ×2
                                                         → слот srv:1101:00044d до 377, gen 1
rec-srv   put rec/slots/r-srv-1 cas=1070                 → index 1072   srv:1102:00044e, gen 2
rec-srv   GET domain/vms/upstream ×2                     → пусто
gw        GET domain/keys, domain/revoked                → токен Бориса проверен заново
gw        RTSP rtsp://…/ingest/SN-A → srv:8091           → 200
push-ca   GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 have 1757500332; 200 10
fwd-ra    GET /ingest/SN-A/poll → srv:8091               → 200 push true, новое поколение 61818027410
fwd-ra    POST /ingest/SN-A/live                         → 200 10
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
push-ca   GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 have 1757500332; 200 10
fwd-ra    GET /ingest/SN-A/poll; POST /ingest/SN-A/live  → 200 push true; 200 10
fwd-ra    GET /ingest/SN-A2/poll                         → 200 push false
          Борис получил 20 кадров; приёмник центра: received 20, viewers 1, recorders 0
          чтения: rec-srv 18, rec-ra 12 и другие — 76

── 10.9 резервный офис relay-b2 ───────────────────────────────────────────────────────────────── (10.9)
anna      POST /api/login                                → 200 «токен 1»
ag-rb2    GET /api/carry/relay-b2 → srv:8071             → 403 «relay-b2 is no member with a key: …»   стук
anna      GET /domain/members                            → 200 rev 5, knocking: relay-b2, 2b075357ba2ff716
anna      POST /domain/members {relay-b2, fingerprint 2b075357ba2ff716}  → 200 rev 6
dcon      GET /api/holder; put domain/members cas=1020   → index 1062
anna      PUT /domain/grants/relay-b2 {anna admin *}     → 200 cluster relay-b2, lines 1
dcon      GET /api/holder; put domain/grants/relay-b2 cas=""  → index 1063
          свёрнуто: проход держателя, агент relay-b2 несёт своё
anna      POST /rec/volumes {disk, kind backup} → relay-b2:8080  → 201
con-rb2   put rec/volumes/disk cas=""                    → index 7012
rec-rb2   put rec/slots/r-relay-b2-1 cas=""              → index 7013
anna      POST /rec/recordings {SN-A, ref:SN-A, when offline, home disk} → relay-b2:8080  → 201
con-rb2   put rec/idem/relay-b2-SN-A cas="", cas=7014    → index 7014, 7015
con-rb2   put rec/recordings/SN-A cas=""                 → index 7016
con-rb2   put rec/idem/relay-b2-SN-A cas=7015            → index 7017
          60 с свёрнуто: регистратор relay-b2, контроллер записей, агенты, проходы держателя
vmsd      put domain/vms/worker cas=1121                 → index 1122
vmsd      GET /kid ×9                                    → 200 fc357029
ag-ra     GET /api/held ×3; GET /api/carry/relay-a       → 200
ag-ra     put domain/vms/sources cas=2083                → index 2090
ag-ra     PUT /domain/members/relay-a/o/rec/heartbeats/…, o/rec/polled/…, reported  → 200
ag-ra     GET /api/carry/relay-a?for=cam-a, ?for=cam-a2  → 200
ag-ca     GET /api/carry/cam-a → relay-a:8446            → 200
ag-ca     PUT /domain/members/cam-a/o/…×3, p/alarms, reported  → 200
          книга основных cam-a: ingest relay-a:8091 до 1757586645, backup relay-b2:8091 до 1757586727
          relay-a выключен
push-ca   GET /ingest/SN-A/poll {version -1} → relay-b2:8091  → …
rec-rb2   put objects/rec/ingest/clock/SN-A.json cas=null  → index 7071
push-ca   ← 200 push true, version 1008433759008
push-ca   POST /ingest/SN-A/live  «токен 2: aud=ingest:relay-b2»  → 200 10   382.1…383.0
          «the backup: the primary does not take the stream»; 30 с свёрнуто
          relay-b2: received 310, recorders 1, written_through 413; relay-a включён
push-ca   GET /ingest/SN-A/poll → relay-a:8091           → 200 push true, have 1757500382
push-ca   POST /ingest/SN-A/live                         → 200 10      413.1…414.0
          чтения: vmsd 84, sig 62, ag-ra 40, ag-ca 38, con-rb2 24, dcon 21 и другие — 352

── 10.10 член уходит: cam-a2 ──────────────────────────────────────────────────────────────────── (10.10)
anna      POST /api/login                                → 200 «токен 1»
anna      DELETE /domain/members/cam-a2                  → 200 rev 6 без cam-a2
dcon      GET /api/holder; put domain/members cas=1020   → index 1062
vmsd      put domain/vms/worker cas=1056                 → index 1063
vmsd      put domain/vms/sources/relay-a, /relay-b       → index 1064, 1065
vmsd      GET /kid ×2; put domain/vms/primaries/cam-a cas=1047  → index 1066
vmsd      GET /kid ×4; put domain/vms/asks/cam-a2, /relay-a      → index 1067, 1068
ag-ra     GET /api/held ×3; GET /api/carry/relay-a       → 200   topology via cam-a2 ещё есть; upstream SN-A2
ag-ra     put domain/member-list cas=2007                → index 2047
ag-ra     put domain/vms/asks cas=2044                   → index 2048
ag-ra     put domain/vms/sources cas=2025                → index 2049
ag-ra     PUT /domain/members/relay-a/reported           → 200
ag-ra     GET /api/carry/relay-a?for=cam-a               → 200
ag-ra     GET /api/carry/relay-a?for=cam-a2              → 404 «cam-a2 is no member of this domain: nothing is carried for it»
ag-ca2    GET /api/carry/cam-a2 → relay-a:8446           → 403 «the domain refuses cam-a2 to relay-a: …»
anna      GET /domain/vms/cameras                        → 200 clusters без cam-a2, complete true; строка SN-A2 осталась
          чтения: vmsd 73, sig 72, ag-ra 40, dcon 15 и другие — 220
```

## Все ключи, которые пишет сценарий

Каждый ключ хранилища и флеша камер, который пишет хоть одна сцена, — в порядке первой записи. Хвост `/<член>` — по ключу на член у держателя; `<ref>` — по ключу на камеру; `-…` в метке — тот же процесс на любом кластере.

| Ключ | Кто пишет | Где | Сцены |
|---|---|---|---|
| `domain/signer` | `sig`, `sig-ra` | хранилище | 1, 10.5, 10.6 |
| `domain/keys` | `sig`, `ag-…`, `sig-ra` | флеш камеры, хранилище | 1, 3, 10.5 |
| `domain/holder` | `sig`, `ag-…`, `sig-ra` | флеш камеры, хранилище | 1, 3, 10.5 |
| `domain/users/anna` | `op-…`, `sig-ra` | хранилище | 1, 10.5 |
| `domain/grants/domain` | `op-…`, `dcon`, `sig-ra` | хранилище | 1, 3, 10.5 |
| `domain/member-key` | `ag-…` | флеш камеры, хранилище | 1, 2 |
| `domain/vms/worker` | `vmsd` | хранилище | 1, 2, 3, 5, 7, 11, 10.4, 10.7, 10.9, 10.10 |
| `domain/vms/stream-accounts/<член>` | `vmsd` | хранилище | 1, 3 |
| `domain/root` | `ag-…` | флеш камеры, хранилище | 1, 3 |
| `domain/vms/stream-accounts` | `ag-…` | флеш камеры, хранилище | 1, 3 |
| `domain/member` | `ag-…` | флеш камеры, хранилище | 1, 3 |
| `domain/members` | `op-…`, `dcon`, `sig-ra` | хранилище | 3, 10.5, 10.9, 10.10 |
| `domain/topology` | `dcon`, `ag-…`, `sig-ra` | флеш камеры, хранилище | 3, 10.5 |
| `domain/grants/<член>` | `dcon`, `sig-ra` | хранилище | 3, 10.5, 10.9 |
| `domain/users/boris` | `sig`, `sig-ra` | хранилище | 3, 10.5 |
| `identity/pointer` | `sig` | хранилище | 3 |
| `domain/grants` | `ag-…` | хранилище | 3 |
| `domain/member-list` | `ag-…` | флеш камеры, хранилище | 3, 10.5, 10.10 |
| `vms/epoch/1` | `cam-…` | флеш камеры | 4, 10.7 |
| `vms/cameras/1` | `cam-…` | флеш камеры | 4 |
| `rec/volumes/card` | `cam-…` | флеш камеры | 4 |
| `rec/recordings/1-sd` | `con-…` | флеш камеры | 4 |
| `rec/slots/r-1` | `card-…` | флеш камеры | 4, 10.7 |
| `rec/holds/card` | `card-…` | флеш камеры | 4, 10.7 |
| `rec/placement/1-sd` | `rctl-…` | флеш камеры | 4 |
| `rec/workers/r-1` | `rctl-…` | флеш камеры | 4 |
| `rec/epoch/1-sd` | `card-…` | флеш камеры | 4, 10.7 |
| `domain/keepers/<член>` | `sig` | хранилище | 5, 11, 12, 10.4 |
| `rec/volumes/disk` | `con-…` | хранилище | 6, 10.9 |
| `rec/slots/r-<кластер>-1` | `rec-…` | хранилище | 6, 9, 10.8, 10.9 |
| `rec/idem/<кластер>-<ref>` | `con-…` | хранилище | 6, 10.9 |
| `rec/recordings/<ref>` | `con-…` | хранилище | 6, 10.9 |
| `rec/holds/disk` | `rec-…` | хранилище | 6, 9 |
| `objects/rec/used/disk` | `rec-…` | хранилище | 6 |
| `rec/placement/<ref>` | `rctl-…` | хранилище | 6 |
| `rec/workers/r-<кластер>-1` | `rctl-…` | хранилище | 6 |
| `rec/epoch/<ref>` | `rec-…` | хранилище | 6, 9 |
| `domain/vms/crossings` | `vmsd`, `sig-ra` | хранилище | 7, 10.5 |
| `domain/vms/sources/<член>` | `vmsd` | хранилище | 7, 10.4, 10.7, 10.10 |
| `domain/vms/primaries/<член>` | `vmsd` | хранилище | 7, 10.4, 10.7, 10.10 |
| `domain/vms/polls/<член>` | `vmsd` | хранилище | 7 |
| `domain/vms/upstream/<член>` | `vmsd` | хранилище | 7 |
| `domain/vms/sources` | `ag-…` | хранилище | 8, 10.1, 10.4, 10.9, 10.10 |
| `domain/vms/upstream` | `ag-…` | хранилище | 8 |
| `domain/vms/primaries` | `ag-…` | флеш камеры | 8, 10.1, 10.4 |
| `domain/backup-taken` | `ag-…` | флеш камеры | 8, 10.1, 10.4 |
| `objects/rec/ingest/clock/<ref>.json` | `rec-…` | хранилище | 9, 11, 10.9 |
| `objects/rec/ingest/up/<ref>.json` | `rec-…` | хранилище | 10, 11 |
| `domain/shared` | `sig`, `ag-…`, `sig-ra` | флеш камеры, хранилище | 11, 10.5 |
| `domain/vms/asks/<член>` | `vmsd` | хранилище | 11, 10.4, 10.7, 10.10 |
| `domain/vms/asks` | `ag-…` | флеш камеры, хранилище | 11, 10.1, 10.4, 10.10 |
| `domain/revoked` | `sig-ra`, `ag-…` | хранилище | 10.5 |
| `domain/stranded` | `sig` | хранилище | 10.6 |

## Итог по числам

Запросы каждой сцены, посчитанные по полной трассе. «Хранилище» — `configstore` и флеш камер вместе; «сеть» — HTTP курса и вызовы приёмника; «объекты» — запросы к объектам держателя или офиса и файлы.

| Сцена | Часть | Чтения хранилища | Записи хранилища | Сеть | Объекты |
|---|---|---|---|---|---|
| 1 домен основан | 2 | 107 | 13 | 1 | 16 чтений, 1 файл |
| 2 члены стучатся | 3 | 64 | 6 | 3 | — |
| 3 приём, топология, права | 3 | 288 | 31 | 27 | 1 |
| 4 камера загружается | 4 | 103 | 10 | 0 | — |
| 5 домен узнаёт камеры | 4 | 318 | 3 | 11 | 19 |
| 6 офис готов писать | 5 | 88 | 14 | 4 | — |
| 7 кто пишет SN-A | 6 | 76 | 9 | 6 | — |
| 8 книги уходят домой | 6 | 153 | 4 | 7 | 4 |
| 9 поток пошёл | 7 | 149 | 14 | 6 | — |
| 10 Борис смотрит | 8 | 104 | 3 | 19 | — |
| 11 сценарий | 9 | 337 | 12 | 30 | 9 |
| 12 тревога | 9 | 225 | 2 | 10 | 7 |
| 10.1 офис выключен | 10 | 295 | 4 | 14 | 9 |
| 10.2 обрыв камера — офис | 10 | 79 | 0 | 6 | — |
| 10.3 обрыв офис — центр | 10 | 109 | 0 | 15 | 4 |
| 10.4 центр выключен | 10 | 452 | 14 | 31 | 10 |
| 10.5 держатель перенесён | 10 | 210 | 23 | 15 | 2 (оба — `no answer`) |
| 10.6 старый держатель вернулся | 10 | 302 | 2 | 13 | 8 |
| 10.7 камера перезагрузилась | 10 | 329 | 11 | 18 | 9 |
| 10.8 регистратор центра | 10 | 76 | 1 | 14 | — |
| 10.9 резервный офис | 10 | 352 | 11 | 30 | 8 |
| 10.10 член уходит | 10 | 220 | 10 | 18 | 1 |

Сколько стоит один проход каждого процесса, видно по повторяющимся блокам:

| Проход | Чтения хранилища | Записи | Сеть | Объекты |
|---|---|---|---|---|
| подписывающий, домен из шести членов | около 55–60 | 0, раз в 30 с — указатели копии | — | отчёты членов |
| воркер VMS на домене | 59–84 | слот и изменившиеся книги | `GET /kid` на каждый токен в книгах | — |
| агент офиса | 38–43 | только изменившиеся строки | `/api/held` ×3, `carry` ×1 + по одному на камеру | отчёт 3–7 `PUT` + сводный |
| агент камеры | 36–38 | только изменившиеся строки | `carry` ×1 у двери офиса | 3–7 `PUT` в объекты офиса |
| шаг камеры с потоком | 1–2 | — | опрос + толчок | — |
| передатчик офиса | — | слово центра, когда меняется | опрос + толчок на каждую камеру из `upstream` | — |

Почему агент читает почти сорок строк, если пишет одну-две: он сверяет каждую принесённую строку с той, что лежит дома, и пишет, только если изменилось то, что строка **говорит** ([справочник](01-reference.md), «`/api/carry`»). А подписывающий читает одни и те же строки по нескольку раз за проход: у прохода держателя нет памяти прохода, и каждый шаг читает своё сам (раздел [2.6](02-founding-the-domain.md)). Что из этого вырастает на сотнях членов, — [часть 12](12-limits-and-scale.md).

---

[← карта разбора](README.md) · назад: [12-limits-and-scale.md](12-limits-and-scale.md)

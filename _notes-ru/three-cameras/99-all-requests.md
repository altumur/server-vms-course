---
genre: записки
kind: разбор кода
subject: М11_Cluster
source-commit: 970e5a7
date: 2026-10-04
status: draft
---

# Приложение. Все запросы сценария одним списком

> [!note] Записки поверх репозитория, а не его документация
> Это разбор: я читал код и восстанавливал по нему, как всё устроено, максимально простыми словами.
> **Источник истины — код.** Где записки расходятся с кодом, прав код.
> Проект описывает себя сам: [`README.md`](../../README.md) и указатели модулей.
> Состояние: коммит `970e5a7`, 4 октября 2026.

[← карта разбора](README.md) · назад: [10-limits-and-scale.md](10-limits-and-scale.md)


Порядок — временной, по частям. Список собран заново из трасс, по которым написаны части 2–8: настоящий код курса на стенде из трёх серверов, `srv-a`, `srv-b`, `srv-c`. Где трасса сворачивает повтор («коротко — только записи»), он свёрнут и здесь. Ответы сокращены до существенного. Индексы `index` и время, как и везде в разборе, условные. **Каждая часть — свой прогон с нуля**, поэтому номера `index` между частями не продолжаются: в части 3 камеры записаны с `index` 1010, 1015, 1020, а в частях 4–7 те же камеры — 1008, 1010, 1012. Это не ошибка и не другие камеры; сверять номера можно только внутри одной части. В скобках справа от заголовка блока — раздел, где запросы разобраны.

**Кто спрашивает** (первая колонка):

| Метка | Кто | Куда идут его запросы к хранилищу |
|---|---|---|
| `OP` | браузер оператора `anna` (в 8.2 ещё `boris`) → консоль, HTTP `:8080` | — |
| `con` | консоль (`vms-console`) на `srv-a`, в части 6 — на `srv-b`; в 8.2 две: `con-a` и `con-b` | `/run/configstore/console.sock` |
| `ctl` | контроллер на `srv-a` | `/run/configstore/vmscontroller.sock` |
| `w-srv-a-1` … | воркер, юнит `vms-vmsworker` своего сервера; `w-2` — запасной на `srv-c` из шаблона `vms-vmsworker-spare@1` | `/run/configstore/vmsworker.sock` |
| `res-a` … | ресурс платформы (`w2c-resource`) на `srv-a`, `srv-b`, `srv-c`; каждые 15 с переписывает `at` в строке своей двери `platform/doors/<srv>` | `/run/configstore/resource.sock` |
| `root` | администратор на `srv-a` | `/run/configstore/admin.sock` |

**Как читать строку.** `GET /v1/get?key=…` и `GET /v1/list?prefix=…` — чтения хранилища ключей (`configstore`). `POST /v1/write put <ключ> cas=…` — запись: `cas=""` значит «только создать», `cas=N` — «только если версия ещё N»; ответ `index N` — новая версия ключа, `409` — конфликт CAS. `пусто` — ключа нет: хранилище отвечает `200 {"items": null, "index": ""}`, а не 404.

Объекты — не ключи хранилища. `GET /v1/objects…?scope=cluster` — запрос к ресурсу **своего** сервера: он отдаёт объект или список объектов всего кластера и сам ходит за чужими файлами к ресурсам других серверов. `FILE <ключ>` — файл объекта, записанный на своём сервере. Размеры heartbeat'а воркера даны, как в юните (`ARCHIVE=/data/platform/events`); на стенде путь `archive` — временный каталог, и ресурс отвечает размером на 61 Б больше (509 → 570, 761 → 822).

Строка слота `vms/slots/<w>` во всех записях и чтениях несёт `server` — сервер держателя (`"server": "srv-a"`); ниже это поле не повторяется.

Чтения `domain/*` консоли (`domain/keys`, `member`, `root`, `grants`, `revoked`, `break_glass` — проверка доступа, обычно дважды на HTTP-запрос) схлопнуты в одну строку `×N domain/*`. Полностью они показаны только в 3.2.

```
── 2.2 воркеры берут имена ───────────────────────────────────────────────────────────────── (2.2)
w-srv-a-1 GET  /v1/get?key=platform/schema                     → пусто          формат хранилища мой
w-srv-a-1 GET  /v1/get?key=platform/decommission/srv-a         → пусто          мой сервер не списан
w-srv-a-1 GET  /v1/list?prefix=vms/slots/                      → {}
w-srv-a-1 GET  /v1/get?key=vms/slots/w-srv-a-1                 → пусто
w-srv-a-1 POST /v1/write put vms/slots/w-srv-a-1 cas=""         → index 1004     holder srv-a:4101, until t0+45, gen 1,
                                                                               server srv-a
res-a     GET  /v1/list?prefix=platform/doors/                  → srv-a, srv-b, srv-c  (записаны первыми heartbeat'ами ресурсов)
res-a     GET  /v1/get?key=platform/doors/srv-b                 → url http://srv-b:8090, since, at   …и srv-c: где отвечают
                                                                               чужие ресурсы и когда отметились
w-srv-a-1 GET  /v1/objects/vms/contenders/w-srv-a-1/machine-id-srv-a?scope=cluster → 404   с другой машины это имя
                                                                               никто не берёт (машина — /etc/machine-id)
w-srv-a-1 GET  /v1/objects/vms/heartbeats/w-srv-a-1?scope=cluster → 404        прошлого отчёта нет
w-srv-b-1 GET  schema, decommission/srv-b                       → пусто
w-srv-b-1 GET  /v1/list?prefix=vms/slots/                      → [w-srv-a-1]
w-srv-b-1 GET  /v1/get?key=vms/slots/w-srv-a-1                 → holder srv-a:4101, released false: занят
w-srv-b-1 GET  /v1/get?key=vms/slots/w-srv-b-1                 → пусто
w-srv-b-1 POST /v1/write put vms/slots/w-srv-b-1 cas=""         → index 1005     server srv-b
res-b     GET  doors: список, srv-a, srv-c
w-srv-b-1 GET  /v1/objects/vms/contenders/w-srv-b-1/machine-id-srv-b?scope=cluster → 404
w-srv-b-1 GET  /v1/objects/vms/heartbeats/w-srv-b-1?scope=cluster → 404
w-srv-c-1 …то же; читает строки w-srv-a-1 и w-srv-b-1 — заняты
w-srv-c-1 POST /v1/write put vms/slots/w-srv-c-1 cas=""         → index 1006     server srv-c
res-c     GET  doors: список, srv-a, srv-b
w-srv-c-1 GET  /v1/objects/vms/contenders/w-srv-c-1/machine-id-srv-c?scope=cluster → 404
w-srv-c-1 GET  /v1/objects/vms/heartbeats/w-srv-c-1?scope=cluster → 404

── 2.3 первый heartbeat каждого воркера ───────────────────────────────────────────────────── (2.3)
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         509 Б: status [], server srv-a,
                                                                                labels vlan:cctv, capacity 50, headroom 50,
                                                                                archive /data/platform/events, present true
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         то же, файл на srv-b
w-srv-c-1 FILE vms/heartbeats/w-srv-c-1                                         то же, файл на srv-c

── 2.4 ресурсы отчитываются о дисках и процессах ──────────────────────────────────────────── (2.4)
res-a     FILE platform/resources/srv-a/heartbeat                               649 Б: space, volumes, waits, restore;
                                                                                workers {vms: [w-srv-a-1]}, running {vms:
                                                                                [w-srv-a-1]}, running_instances [srv-a_4101]
res-b     FILE platform/resources/srv-b/heartbeat
res-c     FILE platform/resources/srv-c/heartbeat
          каждые 15 с ресурс ещё переписывает свою дверь: POST /v1/write put platform/doors/<srv> cas=null, новый at
          (видно в 8.4 и 8.6)

── 2.5 проход контроллера по пустому кластеру: 18 чтений, 0 записей, 11 объектных, 2 файла ── (2.5)
ctl       GET  /v1/objects/vms/controller/pass?scope=cluster    → 404          прошлого отчёта прохода нет
ctl       GET  /v1/list?prefix=platform/decommission/          → {}           списывать некого
ctl       GET  /v1/list?prefix=vms/decommissioned/             → {}
ctl       GET  /v1/list?prefix=vms/slots/                      → три слота
ctl       GET  /v1/get?key=vms/slots/w-srv-a-1                 → holder srv-a:4101, until t0+45, released false, server srv-a
ctl       GET  /v1/objects/vms/heartbeats/w-srv-a-1?scope=cluster → 509 Б, X-Server srv-a
          …то же для w-srv-b-1 и w-srv-c-1 (их файлы на srv-b и srv-c, ресурс srv-a приносит их сам)
ctl       GET  /v1/list?prefix=vms/placement/                  → {}
ctl       GET  /v1/list?prefix=vms/workers/                    → {}
ctl       GET  /v1/list?prefix=vms/cameras/                    → {}
ctl       GET  /v1/list?prefix=vms/servers/                    → {}           меток серверов из консоли нет
ctl       GET  /v1/objects?prefix=vms/heartbeats/&scope=cluster → 3 файла, по одному на сервере
ctl       GET  /v1/get?key=vms/servers/srv-a … srv-c   ×3      → пусто        метки берутся из heartbeat'ов (LABELS)
ctl       GET  /v1/objects?prefix=platform/resources/&scope=cluster → 3 файла
ctl       GET  /v1/objects/platform/resources/srv-a/heartbeat?scope=cluster → 649 Б   …и srv-b, srv-c
ctl       GET  /v1/get?key=vms/policy                          → пусто
ctl       GET  /v1/get?key=platform/drain                      → пусто        никого не выводят
ctl       GET  /v1/get?key=vms/workers/w-srv-a-1 … w-srv-c-1 ×3 → пусто      назначений нет
ctl       GET  /v1/objects?prefix=vms/contenders/&scope=cluster → {}          спора за имена нет
ctl       FILE vms/controller/pass                                              ok true, unplaced 0, name_conflicts 0,
                                                                                spares_withheld {}, reach_budget 10
ctl       GET  /v1/objects?prefix=vms/snapshot/&scope=cluster  → {}
ctl       FILE vms/snapshot/unplaced                                            75 Б: неразмещённых нет

── состояние перед приходом оператора ─────────────────────────────── (2, «Состояние хранилища…»)
root      GET  /v1/list?prefix=                                → 6 ключей: platform/doors/srv-a..c (1001–1003),
                                                                 vms/slots/w-srv-a-1..w-srv-c-1 (1004–1006)
root      GET  /v1/get?key=…  ×6                               → строки дверей и слотов, как выше
root      GET  /v1/objects?prefix=&scope=cluster               → 8 файлов: на srv-a — ресурс, pass, heartbeat
                                                                 w-srv-a-1, snapshot/unplaced; на srv-b и srv-c —
                                                                 ресурс и heartbeat воркера
root      GET  /v1/list?prefix=objects/                        → {}           объектов в хранилище ключей нет

── 3.2 создание камеры 1 «Ворота»: 18 чтений, 5 записей ──────────────────────────────── (3.1–3.3)
OP        POST /cameras  Idempotency-Key: k-anna-0001           → 201  id 1, revision 1, worker null
con       GET  /v1/get?key=domain/keys, member, root, grants, revoked, break_glass  → пусто   кто звонит
con       GET  /v1/get?key=domain/… те же шесть                → пусто        можно ли ему: доступ открыт
con       POST /v1/write put vms/idem/k-anna-0001 cas=""        → index 1007     state pending, sub anna, sha256
con       GET  /v1/list?prefix=vms/idem/                       → [k-anna-0001]  подчистка старых ключей
con       GET  /v1/get?key=vms/idem/k-anna-0001                → свежий — оставить
con       GET  /v1/get?key=vms/next_id                         → пусто
con       POST /v1/write put vms/next_id cas=""                 → index 1008     n 1
con       POST /v1/write put vms/idem/k-anna-0001 cas=1007      → index 1009     id "1" зарезервирован в ключе
con       GET  /v1/list?prefix=vms/cameras/                    → {}           источник не занят
con       POST /v1/write put vms/cameras/1 cas=""               → index 1010     revision 1, labels vlan:cctv
con       GET  /v1/get?key=vms/retention/1                     → пусто        срок не задан — не пишется
con       GET  /v1/get?key=vms/alarms_retention/1              → пусто        то же
con       POST /v1/write put vms/idem/k-anna-0001 cas=1009      → index 1011     state done, status 201, тело ответа

── 3.5 камера 2 «Парковка»: 17 чтений, 5 записей ──────────────────────────────────────────── (3.5)
OP        POST /cameras  Idempotency-Key: k-anna-0002           → 201  id 2
con       GET  ×12 domain/* (проверка доступа)
con       POST /v1/write put vms/idem/k-anna-0002 cas=""        → index 1012
con       GET  /v1/get?key=vms/next_id                         → n 1 @1008      подчистки idem нет: раз в минуту
con       POST /v1/write put vms/next_id cas=1008               → index 1013     n 2
con       POST /v1/write put vms/idem/k-anna-0002 cas=1012      → index 1014     id "2"
con       GET  /v1/list?prefix=vms/cameras/ и /v1/get?key=vms/cameras/1 → источник другой
con       POST /v1/write put vms/cameras/2 cas=""               → index 1015
con       GET  retention/2, alarms_retention/2                 → пусто
con       POST /v1/write put vms/idem/k-anna-0002 cas=1014      → index 1016     state done

── 3.5 камера 3 «Склад»: 18 чтений, 5 записей ─────────────────────────────────────────────── (3.5)
OP        POST /cameras  Idempotency-Key: k-anna-0003           → 201  id 3
          те же запросы; проверка источника читает cameras/1 и cameras/2
con       POST /v1/write put vms/idem/k-anna-0003 cas=""        → index 1017
con       POST /v1/write put vms/next_id cas=1013               → index 1018     n 3
con       POST /v1/write put vms/idem/k-anna-0003 cas=1017      → index 1019     id "3"
con       POST /v1/write put vms/cameras/3 cas=""               → index 1020
con       POST /v1/write put vms/idem/k-anna-0003 cas=1019      → index 1021     state done

── 4 проход контроллера, размещающий три камеры: 31 чтение, 6 записей, 12 объектных, 5 файлов ── (4.1–4.5)
ctl       GET  /v1/objects/vms/controller/pass?scope=cluster    → 775 Б        отчёт прошлого прохода
ctl       GET  /v1/list?prefix=platform/decommission/          → {}
ctl       GET  /v1/list?prefix=vms/decommissioned/             → {}
ctl       GET  /v1/list?prefix=vms/slots/                      → три слота
ctl       GET  /v1/get?key=vms/slots/w-srv-X-1 + /v1/objects/vms/heartbeats/w-srv-X-1  ×3 → живы
ctl       GET  /v1/list?prefix=vms/placement/                  → {}
ctl       GET  /v1/list?prefix=vms/workers/                    → {}
ctl       GET  /v1/list?prefix=vms/cameras/                    → cameras/1..3 (1008, 1010, 1012)
ctl       GET  /v1/get?key=vms/cameras/1 … 3   ×3              → строки камер, labels vlan:cctv
ctl       GET  /v1/get?key=vms/placement/1                     → пусто        решения нет
ctl       GET  /v1/objects?prefix=vms/heartbeats/&scope=cluster → 3 файла
ctl       GET  /v1/objects?prefix=platform/resources/&scope=cluster → 3 файла
ctl       GET  /v1/objects/platform/resources/srv-X/heartbeat?scope=cluster ×3 → 649 Б: ресурсы живы
ctl       GET  /v1/get?key=vms/policy                          → пусто
ctl       GET  /v1/get?key=platform/drain                      → пусто
ctl       GET  /v1/list?prefix=vms/servers/                    → {}
ctl       GET  /v1/get?key=vms/servers/srv-a … srv-c   ×3      → пусто        метки — из heartbeat'ов
ctl       GET  /v1/objects?prefix=rec/heartbeats/&scope=cluster → {}          записи нет — «дома» нет
ctl       GET  /v1/get?key=vms/workers/w-srv-a-1 … w-srv-c-1 ×3 → пусто      нагрузка 0 у всех
ctl       POST /v1/write put vms/placement/1 cas=""             → index 1013     worker w-srv-a-1, reason «most free
                                                                               capacity (50) among 3 worker(s)…»  ← сначала
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=""       → index 1014     units "1", rev 1               ← потом
ctl       GET  /v1/get?key=vms/placement/2                     → пусто
ctl       GET  /v1/get?key=vms/workers/w-srv-a-1               → units "1"    у w-srv-a-1 нагрузка 1
ctl       POST /v1/write put vms/placement/2 cas=""             → index 1015     w-srv-b-1
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=""       → index 1016     units "2", rev 1
ctl       GET  /v1/get?key=vms/placement/3                     → пусто
ctl       GET  /v1/get?key=vms/workers/w-srv-b-1               → units "2"
ctl       POST /v1/write put vms/placement/3 cas=""             → index 1017     w-srv-c-1
ctl       POST /v1/write put vms/workers/w-srv-c-1 cas=""       → index 1018     units "3", rev 1
ctl       GET  /v1/get?key=vms/placement/1 … 3   ×3            → решения, только что записанные
ctl       GET  /v1/list?prefix=vms/placement/                  → 1013, 1015, 1017
ctl       GET  /v1/get?key=vms/workers/w-srv-c-1               → units "3"
ctl       GET  /v1/objects?prefix=vms/contenders/&scope=cluster → {}
ctl       FILE vms/controller/pass                                              unplaced 0, units_short 0
ctl       GET  /v1/objects?prefix=vms/snapshot/&scope=cluster  → [unplaced]
ctl       FILE vms/snapshot/w-srv-a-1                                           389 Б: камера 1, server srv-a
ctl       FILE vms/snapshot/w-srv-b-1                                           401 Б: камера 2
ctl       FILE vms/snapshot/w-srv-c-1                                           383 Б: камера 3
ctl       FILE vms/snapshot/unplaced                                            снова пустой

── 5 воркеры забирают камеры: у каждого 3 чтения, 1 запись, 1 файл ────────────────────── (5.1–5.5)
w-srv-a-1 GET  /v1/get?key=vms/workers/w-srv-a-1               → units "1", rev 1 @1014
w-srv-a-1 GET  /v1/get?key=vms/cameras/1                       → revision 1 @1008
w-srv-a-1 GET  /v1/get?key=vms/epoch/1                         → пусто        эпохи нет
w-srv-a-1 POST /v1/write put vms/epoch/1 cas=""                 → index 1019     epoch 1
          пайплайн: ни одного запроса к хранилищу
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         761 Б: running, observed_revision 1,
                                                                                epoch 1, headroom 49, present true
w-srv-b-1 POST /v1/write put vms/epoch/2 cas=""                 → index 1020     (чтения те же)
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1
w-srv-c-1 POST /v1/write put vms/epoch/3 cas=""                 → index 1021
w-srv-c-1 FILE vms/heartbeats/w-srv-c-1

── продление имени и эпох, lease_pass (раз в ~8 с): 2+K чтений, 1 запись ──────────────── (5.2, 8.6)
w-srv-a-1 GET  /v1/get?key=platform/schema                     → пусто
w-srv-a-1 GET  /v1/get?key=vms/slots/w-srv-a-1                 → holder srv-a:4101 — я, @1004
w-srv-a-1 POST /v1/write put vms/slots/w-srv-a-1 cas=1004       → index 1022     until +45 от сейчас, server srv-a
w-srv-a-1 GET  /v1/get?key=vms/epoch/1                         → epoch 1 — моя     по чтению на каждую камеру
          …то же на w-srv-b-1 и w-srv-c-1

── между проходами, beat_once (каждые 0,25 с): 1 чтение; раз в 30 с — 2 чтения, 1 объектный ─ (5, 10)
w-srv-a-1 GET  /v1/objects?prefix=vms/commands/&scope=cluster  → {}           уборка отметок, раз в 30 с
w-srv-a-1 GET  /v1/list?prefix=objects/vms/commands/           → {}           отметки — строки «только создать»
w-srv-a-1 GET  /v1/list?prefix=vms/requests/                   → {}           заявок нет; этот листинг — каждый раз
          тот же листинг vms/requests/ — и в конце каждого прохода (pump_once)

── 6.1 GET /cameras (консоль на srv-b): 22 чтения, 4 объектных ────────────────────────────── (6.1)
OP        GET  /cameras                                        → 200  rows 3 × running/converged, configured 3
con       GET  ×18 domain/* (проверка доступа)
con       GET  /v1/objects?prefix=vms/heartbeats/&scope=cluster → 3 файла     фактическое
con       GET  /v1/objects/vms/heartbeats/w-srv-X-1?scope=cluster ×3 → 761, 773, 755 Б
con       GET  /v1/list?prefix=vms/cameras/ + /v1/get?key=vms/cameras/1..3   → желаемое

── 6.2 GET /where/1: 18 чтений ────────────────────────────────────────────────────────────── (6.2)
OP        GET  /where/1                                        → 200  worker w-srv-a-1 + reason, directory w-srv-a-1
con       GET  ×12 domain/* (проверка доступа)
con       GET  /v1/get?key=vms/cameras/1                       → есть
con       GET  /v1/get?key=vms/placement/1                     → worker, reason @1013
con       GET  /v1/list?prefix=vms/workers/ + /v1/get?key=vms/workers/w-srv-X-1 ×3 → directory: units "1", "2", "3"

── 6.3 GET /metrics: 8 чтений, 57 объектных ───────────────────────────────────────────────── (6.3)
OP        GET  /metrics                                        → 200  text/plain, 12 094 Б; vms_cameras_running 3;
                                                                 новые серии vms_workers_hung_moved_total,
                                                                 vms_workers_unsure_moved_total, vms_workers_unjudged,
                                                                 vms_units_unjudged, vms_workers_presence_unsaid,
                                                                 vms_name_conflicts, vms_units_left_on_leaving — все 0;
                                                                 vms_spares_withheld — только строка TYPE, без значений
con       GET  /v1/objects?prefix=vms/heartbeats/ + три heartbeat'а  ×8 раз → 32 объектных: каждая серия читает заново
con       GET  /v1/objects?prefix=vms/snapshot/ + снапшоты w-srv-a-1..c-1, /v1/objects/vms/controller/pass → 839 Б
con       GET  /v1/list?prefix=vms/servers/ + /v1/get?key=vms/servers/srv-a..c ×3 → пусто   ×2, с heartbeat'ами
          между ними (ещё 3 × 4 объектных)
con       GET  /v1/objects?prefix=platform/resources/ + три heartbeat'а ресурсов  ×2 → w2c_resources_live 3
          domain/* не читаются: /metrics без проверки доступа

── 7.1 правка камеры 2 (PUT, консоль на srv-a): 22 чтения, 4 записи ──────────────────────── (7.1)
OP        PUT  /cameras/2 {events_retention_days: 30}  Idempotency-Key: k-anna-0004 → 200  revision 2
con       GET  ×12 domain/* (проверка доступа)
con       GET  /v1/get?key=vms/cameras/2   ×5                   → @1010        строка до правки
con       POST /v1/write put vms/idem/k-anna-0004 cas=""        → index 1022
con       GET  /v1/list?prefix=vms/idem/ + /v1/get?key=vms/idem/k-anna-0004   подчистка
con       GET  /v1/get?key=vms/cameras/2                       → @1010
con       POST /v1/write put vms/cameras/2 cas=1010             → index 1023     revision 1→2, events_retention_days 30
con       GET  /v1/get?key=vms/retention/2                     → пусто
con       POST /v1/write put vms/retention/2 cas=""             → index 1024     days 30: поле задано — пишется
con       GET  /v1/get?key=vms/alarms_retention/2              → пусто        поле не задано — не пишется
con       POST /v1/write put vms/idem/k-anna-0004 cas=1022      → index 1025     state done, status 200
w-srv-b-1 GET  /v1/get?key=vms/workers/w-srv-b-1               → units "2"
w-srv-b-1 GET  /v1/get?key=vms/cameras/2                       → revision 2 @1023 → перезапуск под той же эпохой
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         эпохи {2: 1}

── 7.2 удаление камеры 3: 20 чтений, 2 записи; ключа идемпотентности у DELETE нет ─────────── (7.2)
OP        DELETE /cameras/3                                    → 200  {deleted: 3}
con       GET  ×12 domain/* (проверка доступа)
con       GET  /v1/get?key=vms/cameras/3   ×7                   → @1012        есть и не помечена
con       POST /v1/write put vms/cameras/3 cas=1012             → index 1026     та же строка + deleted "true"
con       GET  /v1/get?key=vms/retention/3                     → пусто
con       POST /v1/write put vms/retention/3 cas=""             → index 1027     days 0 — пишется и без срока;
                                                                               alarms_retention не трогается
w-srv-c-1 GET  /v1/get?key=vms/workers/w-srv-c-1               → units "3"    ещё называет её
w-srv-c-1 GET  /v1/get?key=vms/cameras/3                       → deleted @1026 → пайплайн гаснет
w-srv-c-1 FILE vms/heartbeats/w-srv-c-1                                         status []
          проход контроллера: 27 чтений, 2 записи, 12 объектных, 4 файла
ctl       POST /v1/write put vms/workers/w-srv-c-1 cas=1018     → index 1028     units "", rev 2        ← сначала
ctl       POST /v1/write put vms/placement/3 cas=1017           → index 1029     worker "", reason deleted  ← потом
ctl       FILE vms/controller/pass
ctl       FILE vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1
w-srv-c-1 GET  /v1/get?key=vms/workers/w-srv-c-1               → units "", rev 2 @1028
w-srv-c-1 FILE vms/heartbeats/w-srv-c-1
```

## Отказы части 8

В основном сценарии этих запросов нет: каждый блок — то, чем от него отличается один отказ. Каждая сцена — свой прогон с нуля: три камеры созданы и работают, как в конце части 6; правки и удаления части 7 в них нет. Большинство трасс части 8 показывают только записи; чтения в них посчитаны и названы числом.

```
── 8.1 «Сохранить» дважды ────────────────────────────────────────────────────────────────── (8.1)
OP        POST /cameras  Idempotency-Key: k-anna-0001           → 201  id 1   первое нажатие: как в 3.2, idem done @1011
OP        POST /cameras  Idempotency-Key: k-anna-0001           → 201  id 1   второе, то же тело
con       GET  ×12 domain/* (проверка доступа)
con       POST /v1/write put vms/idem/k-anna-0001 cas=""        → 409 conflict, версия 1011   ключ уже занят
con       GET  /v1/get?key=vms/idem/k-anna-0001                → state done, status 201 → тот же ответ; камера одна
OP        POST /cameras  Idempotency-Key: k-anna-0001, name «Ворота-2» → 422 «key reused»
con       GET  ×12 domain/* (проверка доступа)
con       POST /v1/write put vms/idem/k-anna-0001 cas=""        → 409          sha256 тела другой
con       GET  /v1/get?key=vms/idem/k-anna-0001                → sha256 не совпадает → 422

── 8.2 два оператора на разных консолях ───────────────────────────────────────────────────── (8.2)
OP-anna   POST /cameras «Ворота» → консоль srv-a, Idempotency-Key: k-anna-0001 → 201  id 2
OP-boris  POST /cameras «Парковка» → консоль srv-b, Idempotency-Key: k-boris-0001 → 201  id 1
con-a     POST /v1/write put vms/idem/k-anna-0001 cas=""        → index 1007
con-a     GET  /v1/list?prefix=vms/idem/, /v1/get?key=vms/idem/k-anna-0001
con-a     GET  /v1/get?key=vms/next_id                         → пусто
          ── сюда стенд вклинивает весь запрос boris ──
con-b     POST /v1/write put vms/idem/k-boris-0001 cas=""       → index 1008
con-b     GET  /v1/list?prefix=vms/idem/, idem/k-anna-0001, idem/k-boris-0001
con-b     GET  /v1/get?key=vms/next_id                         → пусто
con-b     POST /v1/write put vms/next_id cas=""                 → index 1009     n 1
con-b     POST /v1/write put vms/idem/k-boris-0001 cas=1008     → index 1010     id "1"
con-b     GET  /v1/list?prefix=vms/cameras/                    → {}
con-b     POST /v1/write put vms/cameras/1 cas=""               → index 1011     «Парковка»
con-b     GET  retention/1, alarms_retention/1                 → пусто
con-b     POST /v1/write put vms/idem/k-boris-0001 cas=1010     → index 1012     done
          ── запрос anna продолжается ──
con-a     POST /v1/write put vms/next_id cas=""                 → 409 conflict, версия 1009
con-a     GET  /v1/get?key=vms/next_id                         → n 1 @1009
con-a     POST /v1/write put vms/next_id cas=1009               → index 1014     n 2
con-a     POST /v1/write put vms/idem/k-anna-0001 cas=1007      → index 1015     id "2"
con-a     GET  /v1/list?prefix=vms/cameras/ + /v1/get?key=vms/cameras/1 → источник другой
con-a     POST /v1/write put vms/cameras/2 cas=""               → index 1016     «Ворота»
con-a     GET  retention/2, alarms_retention/2                 → пусто
con-a     POST /v1/write put vms/idem/k-anna-0001 cas=1015      → index 1017     done
con-a/b   GET  ×24 domain/* (проверка доступа, по 12 на запрос)

── 8.3 метка, которой нет ни на одном сервере ─────────────────────────────────────────────── (8.3)
OP        POST /cameras «Касса», labels [vlan:cctv-dmz]  Idempotency-Key: k-anna-0004 → 201  id 4
con       POST /v1/write put vms/idem/k-anna-0004 cas=""        → index 1022
con       POST /v1/write put vms/next_id cas=1011               → index 1023     n 4
con       POST /v1/write put vms/idem/k-anna-0004 cas=1022      → index 1024     id "4"
con       POST /v1/write put vms/cameras/4 cas=""               → index 1025     labels vlan:cctv-dmz
con       POST /v1/write put vms/idem/k-anna-0004 cas=1024      → index 1026     done
          проход контроллера: 26 чтений, 0 записей, 12 объектных, 5 файлов; размещения, назначения и предложения
          слота нет — ни один сервер не покрывает vlan:cctv-dmz, запасному негде встать
ctl       FILE vms/controller/pass                                              unplaced 1, units_short {vlan:cctv-dmz: 1},
                                                                                workers_needed и spare_offers {vlan:cctv-dmz: 0},
                                                                                spares_withheld {vlan:cctv-dmz: «no server a
                                                                                spare could run on reaches vlan:cctv-dmz»}
ctl       FILE vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1
ctl       FILE vms/snapshot/unplaced                                            камера 4
          журнал контроллера (в М11 — лог процесса): тревога spares.no_server {of vms, labels vlan:cctv-dmz}
OP        GET  /unplaceable                                    → 200  [{id 4, labels [vlan:cctv-dmz], workers_live 3}]
con       GET  32 чтения (12 — domain/*), 8 объектных: heartbeat'ы воркеров, слоты, ресурсы,
          vms/policy, platform/drain, platform/decommission/, камеры 1..4, placement/1..4 (4 → пусто), vms/servers/*

── 8.4 замолчал ресурс srv-b ──────────────────────────────────────────────────────────────── (8.4)
          50 с: воркеры продлевают имена и пишут heartbeat'ы, ресурсы srv-a и srv-c тоже; ресурс srv-b молчит
w-srv-a-1 POST /v1/write put vms/slots/w-srv-a-1 cas=1004       → index 1022     until t0+65
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1
w-srv-b-1 POST /v1/write put vms/slots/w-srv-b-1 cas=1005       → index 1023     воркер на srv-b жив
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1
w-srv-c-1 POST /v1/write put vms/slots/w-srv-c-1 cas=1006       → index 1024
w-srv-c-1 FILE vms/heartbeats/w-srv-c-1
res-a     FILE platform/resources/srv-a/heartbeat
res-a     POST /v1/write put platform/doors/srv-a cas=null      → index 1025     at t0+20: дверь отметилась
res-c     FILE platform/resources/srv-c/heartbeat
res-c     POST /v1/write put platform/doors/srv-c cas=null      → index 1026     at t0+20
          …ещё два таких раунда: слоты 1027–1029, двери srv-a/srv-c 1030–1031 (at t0+40); слоты 1032–1034 и
          heartbeat'ы ресурсов без двери. FILE platform/resources/srv-b/heartbeat и дверь srv-b — ни разу
          проход контроллера: 28 чтений, 3 записи, 12 объектных, 4 файла; resource_state(srv-b) = silent
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1035     w-srv-a-1, reason «resource on srv-b
                                                                               silent; most free capacity (49)…»  ← первым
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1036     units ""
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1037     units "1,2", rev 2
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1, w-srv-c-1, w-srv-b-1
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1038     epoch 2: камера 2 теперь здесь
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         эпохи {1: 1, 2: 2}
w-srv-b-1 POST /v1/write put vms/slots/w-srv-b-1 cas=1033       → index 1039     lease_pass: эпоха 2 не его — камеру 2 отдал
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         работает []

── 8.5 воркер один, а не три ──────────────────────────────────────────────────────────────── (8.5)
          проход контроллера: 25 чтений, 6 записей, 10 объектных, 2 файла
ctl       POST /v1/write put vms/placement/1 cas=""             → index 1011     w-srv-a-1, «most free capacity (50)
                                                                               among 1 worker(s)…»
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=""       → index 1012     units "1", rev 1
ctl       POST /v1/write put vms/placement/2 cas=""             → index 1013     w-srv-a-1, capacity (49)
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1012     → index 1014     units "1,2", rev 2
ctl       POST /v1/write put vms/placement/3 cas=""             → index 1015     w-srv-a-1, capacity (48)
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1016     units "1,2,3", rev 3
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1                      workers_needed 0
w-srv-a-1 POST /v1/write put vms/epoch/1, 2, 3 cas=""          → index 1017, 1018, 1019   epoch 1 у каждой
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         работает [1, 2, 3]

── 8.6а упал процесс w-srv-b-1, сервер и ресурс srv-b живы ───────────────────────────────────── (8.6)
          процесс зарегистрирован у ресурса (Worker.present: замок в .workers/); умер — замок отпущен, ресурс
          srv-b пишет: w-srv-b-1 размещён здесь (workers), но не работает (нет в running)
          t+15 с: живые продлевают имена, ресурсы всех трёх серверов пишут heartbeat и дверь
w-srv-a-1 POST /v1/write put vms/slots/w-srv-a-1 cas=1004       → index 1022     until t0+60
w-srv-c-1 POST /v1/write put vms/slots/w-srv-c-1 cas=1006       → index 1023
w-srv-a-1, w-srv-c-1  FILE vms/heartbeats/<свой>
res-a, res-b, res-c   FILE platform/resources/<srv>/heartbeat
res-a, res-b, res-c   POST /v1/write put platform/doors/<srv> cas=null → index 1024, 1025, 1026   at t0+15
          t+40 с: проход — 28 чтений, 0 записей, 12 объектных, 4 файла;
          slot_fate(w-srv-b-1) = alive «holds its name for another 6 s»
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1   (каждый проход)
          t+50 с: слот истёк, ресурс srv-b говорит «процесс не работает» — fate move без запаса SLOT_LOST_AFTER;
          проход с reconcile живых: 33 чтения, 4 записи (одна — эпоха воркера), 12 объектных, 4 файла
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1034     w-srv-a-1, reason «w-srv-b-1's process
                                                                               on srv-b is not running: moved when its slot ran
                                                                               out, its server's resource saying so; …(49)…»
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1035     units "", rev 2
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1036     units "1,2", rev 2
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1037     epoch 2
          t+95 с: 29 чтений, 0 записей, 12 объектных; снова move — уводить уже нечего
          systemd поднимает w-srv-b-1 заново (новый процесс, то же имя)
w-srv-b-1 GET  schema, decommission/srv-b                       → пусто
w-srv-b-1 GET  /v1/list?prefix=vms/slots/ + строки трёх слотов → свой: holder srv-b:4102, until t0+45 — истёк
w-srv-b-1 GET  /v1/get?key=vms/slots/w-srv-b-1                 → @1005
w-srv-b-1 POST /v1/write put vms/slots/w-srv-b-1 cas=1005       → index 1043     holder srv-b:4104, gen 2
w-srv-b-1 GET  /v1/objects/vms/contenders/w-srv-b-1/machine-id-srv-b?scope=cluster → 404
w-srv-b-1 GET  /v1/objects/vms/heartbeats/w-srv-b-1?scope=cluster → 773 Б      прежний отчёт
w-srv-b-1 GET  /v1/get?key=vms/workers/w-srv-b-1               → units "", rev 2   начинает пустым
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         работает []
          (вне трассы: при RestartSec=2 новый процесс успевает до t+45 — берёт имя, gen 2, и камеру 2 под эпохой 2)

── 8.6б обесточен srv-b, контроллер работал всё время ────────────────────────────────────────── (8.6)
          молчат слот w-srv-b-1 и ресурс srv-b; heartbeat'ы с srv-b контроллер помнит с прошлых проходов
          t+50 с: 29 чтений, 0 записей, 12 объектных, 4 файла; resource_state(srv-b) = silent;
          slot_fate = alive «stopped renewing its name 5 s ago; … may still be writing for 41 s more»
          t+95 с: два молчания — fate move; проход с reconcile: 34 чтения, 4 записи, 12 объектных, 4 файла
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1042     w-srv-a-1, reason «server srv-b gone:
                                                                               slot w-srv-b-1 lapsed and its resource silent; …»
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1043     units "", rev 2
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1044     units "1,2", rev 2
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1, w-srv-c-1, w-srv-b-1
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1045     epoch 2
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         работает [1, 2], эпохи {1: 1, 2: 2}

── 8.6в обесточен srv-b, контроллер свежий (первый проход на t+95) ───────────────────────────── (8.6)
          в хранилище с прошлого: vms/slots/w-srv-b-1 @1005 {holder srv-b:4102, until t0+45, server srv-b};
          platform/doors/srv-b @1002 {at t0} — ресурс srv-b больше не отмечался
ctl       GET  /v1/objects/vms/controller/pass?scope=cluster    → 839 Б, X-Missing srv-b
ctl       GET  /v1/list?prefix=platform/decommission/, vms/decommissioned/ → {}
ctl       GET  /v1/list?prefix=vms/slots/                      → три слота (w-srv-a-1 @1038, w-srv-b-1 @1005, w-srv-c-1 @1039)
ctl       GET  /v1/get?key=vms/slots/w-srv-a-1 + /v1/objects/vms/heartbeats/w-srv-a-1 → жив, 761 Б
ctl       GET  /v1/get?key=vms/slots/w-srv-b-1                 → until t0+45, server srv-b — истёк
ctl       GET  /v1/objects/vms/heartbeats/w-srv-b-1?scope=cluster → 404, X-Missing srv-b
ctl       GET  /v1/objects?prefix=platform/resources/&scope=cluster → srv-a, srv-c; missing [srv-b]
ctl       GET  /v1/objects/platform/resources/srv-a/heartbeat, …/srv-c/heartbeat → 649 Б
ctl       GET  /v1/get?key=platform/doors/srv-b                → at t0 — старше 45 с: resource_state silent
ctl       GET  /v1/get?key=vms/slots/w-srv-c-1 + /v1/objects/vms/heartbeats/w-srv-c-1 → жив
ctl       GET  /v1/list?prefix=vms/placement/ + placement/1..3 и cameras/1..3 по очереди
ctl       GET  /v1/list?prefix=vms/workers/ + workers/w-srv-a-1..c-1 ×3 → units "1", "2", "3"
ctl       GET  /v1/list?prefix=vms/cameras/                    → cameras/1..3
ctl       GET  /v1/list?prefix=vms/servers/                    → {}
ctl       GET  /v1/objects?prefix=vms/heartbeats/&scope=cluster → w-srv-a-1, w-srv-c-1; missing [srv-b]
ctl       GET  /v1/get?key=vms/servers/srv-a, srv-c            → пусто        srv-b в списке heartbeat'ов нет
ctl       GET  /v1/get?key=vms/policy, platform/drain          → пусто
ctl       GET  /v1/objects?prefix=rec/heartbeats/&scope=cluster → {}, missing [srv-b]
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1042     w-srv-a-1, «server srv-b gone: slot
                                                                               w-srv-b-1 lapsed and its resource silent; …»
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1043     units "", rev 2
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1044     units "1,2", rev 2
ctl       GET  /v1/get?key=vms/placement/2, workers/w-srv-b-1, workers/w-srv-a-1 → только что записанные
ctl       GET  /v1/objects?prefix=vms/contenders/&scope=cluster → {}, missing [srv-b]
ctl       FILE vms/controller/pass
ctl       GET  /v1/objects?prefix=vms/snapshot/&scope=cluster  → три снапшота, missing [srv-b]
ctl       FILE vms/snapshot/w-srv-a-1, w-srv-c-1, w-srv-b-1
w-srv-a-1 GET  workers/w-srv-a-1 → "1,2"; cameras/1, cameras/2; epoch/2 → epoch 1 @1020
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1045     epoch 2
w-srv-a-1 FILE vms/heartbeats/w-srv-a-1                                         работает [1, 2]
          всего за проход и reconcile живых: 33 чтения, 4 записи, 12 объектных, 4 файла
          (раньше, до поля server в слоте и at в двери, тут было «wait: never said which server» навсегда)

── 8.6г судить нельзя: unsure → unsure_moved ─────────────────────────────────────────────────── (8.6)
          дверь ресурса srv-b не отвечает другим серверам, сам ресурс жив и пишет at в platform/doors/srv-b;
          процесс w-srv-b-1 упал и не поднимается; until слота — t+45
          t+50 с: 25 чтений, 0 записей, 12 объектных, 4 файла; resource_state(srv-b) = unreachable; fate alive
          t+95 с: 25 чтений, 0 записей; fate unsure «…whether the process runs cannot be told: its units stay,
          for up to 900 s»; отчёт: workers_unjudged [w-srv-b-1], units_unjudged 1;
          журнал контроллера: тревога worker.unjudged {worker w-srv-b-1}
res-b     POST /v1/write put platform/doors/srv-b cas=null      → …index 1259    at t0+950 — всё это время отмечается
          t+950 с (until + HUNG_MOVE_AFTER 900 + 5): fate unsure_moved; проход с reconcile: 34 чтения, 4 записи
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1261     w-srv-a-1, «…cannot be told, for 905 s
                                                                               past its slot's end, longer than 900 s: its
                                                                               units move anyway; …»
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1262     units "", rev 2
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1263     units "1,2", rev 2
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1264     epoch 2
          отчёт: workers_unsure_moved_total 1; журнал: тревога worker.unsure_moved {worker w-srv-b-1, after 900}

── 8.6д процесс завис: hung → hung_moved ─────────────────────────────────────────────────────── (8.6)
          w-srv-b-1 жив и держит замок у ресурса srv-b, но не продлевает имя и не пишет heartbeat (SIGSTOP);
          ресурс srv-b жив и говорит: работает. В юните WatchdogSec=360 убил бы его раньше — тогда это 8.6а
          t+50 с: 24 чтения, 0 записей, 12 объектных, 4 файла; fate alive
          t+95 с: 24 чтения, 0 записей; fate hung «…its process runs on srv-b: hung, or cut off from the store —
          its units stay, so they get no second writer, for up to 900 s»; workers_hung [w-srv-b-1];
          журнал: тревога worker.hung
          t+950 с: fate hung_moved; проход с reconcile: 33 чтения, 4 записи
ctl       POST /v1/write put vms/placement/2 cas=1015           → index 1261     w-srv-a-1, «w-srv-b-1 has been hung on
                                                                               srv-b for 905 s, longer than 900 s: its units
                                                                               move anyway; …»
ctl       POST /v1/write put vms/workers/w-srv-b-1 cas=1016     → index 1262     units "", rev 2
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1263     units "1,2", rev 2
w-srv-a-1 POST /v1/write put vms/epoch/2 cas=1020               → index 1264     epoch 2
          отчёт: workers_hung_moved_total 1; журнал: тревога worker.hung_moved {worker w-srv-b-1, after 900}
          зависший процесс оживает (SIGCONT)
w-srv-b-1 GET  /v1/get?key=platform/schema                     → пусто
w-srv-b-1 GET  /v1/get?key=vms/slots/w-srv-b-1                 → holder srv-b:4102, gen 1 — всё ещё я, @1005
w-srv-b-1 POST /v1/write put vms/slots/w-srv-b-1 cas=1005       → index 1265     until t0+995: имя продлено
w-srv-b-1 GET  /v1/get?key=vms/epoch/2                         → epoch 2 @1264 — не моя: камеру 2 теряет
w-srv-b-1 GET  /v1/get?key=vms/workers/w-srv-b-1               → units "", rev 2
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         работает []

          в 8.6г и 8.6д проходы между отметками не запускались; контроллер один, на srv-a

── 8.7 две копии w-srv-a-1 ────────────────────────────────────────────────────────────────── (8.7)
w-srv-a-1² GET schema, decommission/srv-a                       → пусто         вторая копия, srv-a:4104
w-srv-a-1² GET /v1/list?prefix=vms/slots/ + слоты всех трёх, затем свой ещё раз → holder srv-a:4101 @1004
w-srv-a-1² POST /v1/write put vms/slots/w-srv-a-1 cas=1004      → index 1022     holder srv-a:4104, gen 2
w-srv-a-1² GET /v1/objects/vms/contenders/w-srv-a-1/machine-id-srv-a?scope=cluster → 404
w-srv-a-1² GET /v1/objects/vms/heartbeats/w-srv-a-1?scope=cluster → 761 Б
w-srv-a-1² GET /v1/get?key=vms/workers/w-srv-a-1               → units "1"
w-srv-a-1² GET /v1/get?key=vms/cameras/1                       → @1008
w-srv-a-1² GET /v1/get?key=vms/epoch/1                         → epoch 1 @1019
w-srv-a-1² POST /v1/write put vms/epoch/1 cas=1019              → index 1023     epoch 2
w-srv-a-1² FILE vms/heartbeats/w-srv-a-1                                        работает [1] под эпохой 2
w-srv-a-1  GET /v1/get?key=platform/schema                     → пусто         первая копия просыпается
w-srv-a-1  GET /v1/get?key=vms/slots/w-srv-a-1                 → holder srv-a:4104, gen 2 — не я:
                                                                 камеру 1 теряет, recording_allowed false

── 8.8 камер больше, чем ёмкости (в трассе CAPACITY=1) ────────────────────────────────────── (8.8)
con       POST /v1/write put vms/next_id cas=1011               → index 1022     n 4
con       POST /v1/write put vms/cameras/4 cas=""               → index 1023     «Касса», vlan:cctv
          консоль и проход контроллера вместе: 33 чтения, 3 записи, 12 объектных, 5 файлов
ctl       POST /v1/write put vms/slots/w-2 cas=""               → index 1024     предложение: offer vlan:cctv, gen 0
ctl       FILE vms/controller/pass                                              units_short, workers_needed,
                                                                                spare_offers {vlan:cctv: 1}
ctl       FILE vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1, unplaced
          w2c-spares.sh на srv-c читает /metrics: vms_workers_needed{labels="vlan:cctv"} 1, vms_units_short 1,
          vms_spare_offers 1 → под пользователем w2c-spares пишет SPARE_FOR=vlan:cctv в
          /run/w2c-spares/vms-vmsworker-spare@1.service.env и делает systemctl start vms-vmsworker-spare@1
          (шаблон — юнит воркера без WORKER_NAME, RTSP_PORT=auto; w2c-run.sh берёт из файла только SPARE_FOR=)
w-2       POST /v1/write put vms/slots/w-2 cas=1024             → index 1025     holder srv-c:4104, gen 1, taken_at,
                                                                               server srv-c (запасной: 7 чтений, 1 объектный)
w-2       FILE vms/heartbeats/w-2
          проход контроллера и запасного вместе: 34 чтения, 3 записи, 13 объектных, 7 файлов
ctl       POST /v1/write put vms/placement/4 cas=""             → index 1026     w-2, «most free capacity (1)
                                                                               among 4 worker(s)…; on srv-c»
ctl       POST /v1/write put vms/workers/w-2 cas=""             → index 1027     units "4", rev 1
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1, w-2, unplaced
w-2       POST /v1/write put vms/epoch/4 cas=""                 → index 1028     epoch 1
w-2       FILE vms/heartbeats/w-2                                               работает [4]

── 8.9 строка не читается ─────────────────────────────────────────────────────────────────── (8.9)
root      POST /v1/write put vms/cameras/2 cas=1010             → index 1022     revision «два» (правка руками)
          проход контроллера: 24 чтения, 0 записей, 12 объектных, 4 файла; garbled 1, камера 2 остаётся на w-srv-b-1
ctl       FILE vms/controller/pass, vms/snapshot/w-srv-a-1, w-srv-c-1, w-srv-b-1
w-srv-b-1 GET  /v1/get?key=vms/workers/w-srv-b-1               → units "2"
w-srv-b-1 GET  /v1/get?key=vms/cameras/2                       → revision «два» @1022 — не разбирается
w-srv-b-1 FILE vms/heartbeats/w-srv-b-1                                         камера 2 running по прежней строке,
                                                                                why «its row does not parse…»
OP        GET  /cameras                                        → 200  у камеры 2 в rows то же why

── 8.10 списание сервера srv-c ────────────────────────────────────────────────────────────── (8.10)
OP        POST /servers/srv-c/decommission {why: «srv-c сгорел»} → 409 «server answers»: ресурс слышен 0 с назад
          100 с спустя srv-c молчит
OP        POST /servers/srv-c/decommission {why: «srv-c сгорел»} → 202 state requested,
                                                                 subsystems.vms: workers [w-srv-c-1], units ["3"]
con       21 чтение, 66 объектных, затем
con       POST /v1/write put platform/decommission/srv-c cas=null → index 1034  by anna, why
          проход контроллера: 31 чтение, 5 записей, 12 объектных, 4 файла
ctl       POST /v1/write put vms/slots/w-srv-c-1 cas=1006       → index 1035     released true; поля server в строке
                                                                               нет (free_slot его не пишет)
ctl       POST /v1/write put vms/decommissioned/srv-c cas=null  → index 1036     slots w-srv-c-1, units "3"
ctl       POST /v1/write put vms/placement/3 cas=1017           → index 1037     w-srv-a-1, reason «slot w-srv-c-1
                                                                               released; most free capacity (49)…»
ctl       POST /v1/write put vms/workers/w-srv-c-1 cas=1018     → index 1038     units ""
ctl       POST /v1/write put vms/workers/w-srv-a-1 cas=1014     → index 1039     units "1,3", rev 2
ctl       FILE vms/controller/pass                                              servers_decommissioned [srv-c],
                                                                                slots_released [w-srv-c-1]
ctl       FILE vms/snapshot/w-srv-a-1, w-srv-b-1, w-srv-c-1
```

## Итог по числам

| Что | Хранилище | Объекты | Из них работы |
|---|---|---|---|
| создание камеры 1 | 18 чтений, 5 записей | — | 5 записей и 6 чтений; 12 чтений — `domain/*` |
| создание камеры 2 / камеры 3 | 17 / 18 чтений, по 5 записей | — | подчистки `idem` нет; по чтению на каждую уже заведённую камеру |
| воркер берёт имя (первым, на пустом кластере) | 4 чтения, 1 запись | 2 запроса | слот; `vms/contenders/<w>/<машина>` и прошлый heartbeat — оба 404 |
| проход контроллера по пустому кластеру | 18 чтений, 0 записей | 11 запросов, 2 файла | только отчёт прохода и пустой `unplaced` |
| первый проход контроллера, три камеры | 31 чтение, 6 записей | 12 запросов, 5 файлов | 3 размещения, 3 назначения, снапшот |
| устойчивый проход контроллера, три камеры | 25 чтений, 0 записей | 12 запросов, 4 файла | только отчёт и снапшот |
| проход, уводящий камеру (8.4, 8.6) | 28–34 чтения, 3 записи (+1 — эпоха у нового воркера) | 12 запросов, 4 файла | размещение, два назначения |
| воркер поднимает камеру | 3 чтения, 1 запись | 1 файл | назначение, строка, эпоха — чтение и запись |
| продление воркера (`lease_pass`) | 2 + по чтению на камеру, 1 запись | — | одна запись — слот |
| между проходами (`beat_once`, 0,25 с) | 1 чтение; раз в 30 с — 2 | раз в 30 с — 1 запрос | заявки; раз в 30 с — уборка отметок команд |
| `GET /cameras` / `/where/1` / `/metrics` | 22 / 18 / 8 чтений | 4 / 0 / 57 запросов | `domain/*` — 18, 12 и 0 из них |
| правка | 22 чтения, 4 записи | — | 12 чтений — `domain/*`; ключ идемпотентности страница шлёт и для `PUT` |
| удаление | 20 чтений, 2 записи | — | 12 чтений — `domain/*`; ключа идемпотентности нет вовсе |

Обратите внимание на асимметрию в 7.2: **воркер гасит видео раньше, чем контроллер тронул размещение**. Консоль только помечает строку, воркер на своём проходе её пропускает, а контроллер приходит потом и делает две записи учёта ([часть 7](07-edit-and-delete.md)). И на число чтений прохода контроллера: в устойчивом проходе оно растёт примерно как `2 × камеры + 19`, потому что контроллер читает каждую строку камеры и её размещение заново. Объектных запросов при этом около 12 на проход, сколько бы ни было камер: heartbeat'ы, ресурсы, снапшоты и `vms/contenders/` читаются списком ([4.6](04-placement.md), [часть 10](10-limits-and-scale.md)). Объектные чтения на стенде не кэшируются; в продукте `LIST_FRESH=1.0` с, и запросов будет меньше.

---

[← карта разбора](README.md) · назад: [10-limits-and-scale.md](10-limits-and-scale.md)

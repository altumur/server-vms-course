---
genre: записки
kind: разбор кода
subject: М11_ClusterVMS
source-commit: 2b66bea
date: 2026-10-02
status: draft
---

# Приложение. Все запросы сценария одним списком

> [!note] Записки поверх репозитория, а не его документация
> Это разбор: я читал код и восстанавливал по нему, как всё устроено, максимально простыми словами.
> **Источник истины — код.** Где записки расходятся с кодом, прав код.
> Проект описывает себя сам: [`README.md`](../../README.md) и указатели модулей.
> Состояние: коммит `2b66bea`, 2 октября 2026.

[← карта разбора](README.md) · назад: [10-limits-and-scale.md](10-limits-and-scale.md)


Порядок — временной. Список собран из записей запросов частей 2–8, а не придуман заново: где часть сворачивает повтор («то же для w-2», «×3»), он свёрнут и здесь. Ответы сокращены до существенного. `ModifyIndex` и время, как и везде в разборе, условные; в скобках справа — раздел, где запрос разобран.

```
── подготовка (до прихода оператора) ─────────────────────────────── (2.2–2.5)
w-1  GET  /v1/var/platform/schema                            → 404  формат мой (при старте)
w-1  GET  /v1/vars?prefix=vms/slots/                         → []
w-1  GET  /v1/var/vms/slots/w-1                              → 404
w-1  PUT  /v1/var/vms/slots/w-1?cas=0                        → 1001  holder srv-1:1841:9f3c2a, until +45, gen 1
w-1  GET  /v1/var/objects/vms/heartbeats/w-1                 → 404  прошлого отчёта нет
w-1  PUT  /v1/var/objects/vms/heartbeats/w-1                 → 1002  status [], capacity 50, headroom 50
w-2  GET  /v1/var/platform/schema                            → 404
w-2  GET  /v1/vars?prefix=vms/slots/                         → [w-1]
w-2  GET  /v1/var/vms/slots/w-1                              → занят: until впереди, released false
w-2  GET  /v1/var/vms/slots/w-2                              → 404
w-2  PUT  /v1/var/vms/slots/w-2?cas=0                        → 1003
     …и heartbeat, как у w-1. w-3 читает строки w-1 и w-2 и берёт w-3
res  GET  /v1/var/platform/schema                            → 404  (при старте)
res  PUT  /v1/var/objects/platform/resources/srv-1/heartbeat → 1007  space, volumes, waits
     …то же для srv-2 и srv-3
con  GET  /v1/var/platform/schema                            → 404  (при старте консоли)
ctl  GET  /v1/var/platform/schema                            → 404  (при старте контроллера)

── проход контроллера по пустому кластеру: 77 чтений, 1 запись ────── (2.5)
ctl  GET  /v1/vars?prefix=vms/placement/   ×3                → []   удалённые, завершённые, сверка
ctl  GET  /v1/vars?prefix=vms/workers/                       → []
ctl  GET  /v1/vars?prefix=vms/cameras/                       → []   ensure_placed: 5 чтений
ctl  … redistribute: 35 чтений — heartbeat'ы ×4, слоты ×1, ресурсы ×3 (листинг и три GET каждый раз),
       platform/drain → 404, vms/policy → 404
ctl  … ensure_home(1): 35 чтений — те же, потом листинг камер
ctl  GET  /v1/vars?prefix=vms/cameras/                       → []
ctl  GET  /v1/vars?prefix=objects/vms/snapshot/              → []   шардов ещё нет
ctl  PUT  /v1/var/objects/vms/snapshot/unplaced              → пустой шард: «камер нет»

── создание камеры 1 (T+0.0) ─────────────────────────────────────── (3.1–3.3)
OP   POST /cameras  Idempotency-Key: 8f4b21e0-…              → 201  id 1, worker null
con  GET  /v1/var/domain/keys, member, root, grants, revoked, break_glass   → 404  «кто звонит»
con  GET  /v1/var/domain/… те же шесть                       → 404  «можно ли ему»: консоль открыта
con  PUT  /v1/var/vms/idem/8f4b21e0-…?cas=0                  → 4401  state pending, sub, sha256
con  GET  /v1/vars?prefix=vms/idem/                          → 1 путь   (подчистка, не чаще раза в минуту)
con  GET  /v1/var/vms/idem/8f4b21e0-…                        → свежий — оставить
con  GET  /v1/var/vms/next_id                                → 404
con  PUT  /v1/var/vms/next_id?cas=0                          → 4405  n 1
con  PUT  /v1/var/vms/idem/8f4b21e0-…?cas=4401               → 4407  id "1" в захвате
con  GET  /v1/vars?prefix=vms/cameras/                       → []   источник не занят
con  PUT  /v1/var/vms/cameras/1?cas=0                        → 4409  revision 1, пароль запечатан
con  GET  /v1/var/vms/retention/1                            → 404  срок не задан — не пишется
con  GET  /v1/var/vms/alarms_retention/1                     → 404  то же
con  PUT  /v1/var/vms/idem/8f4b21e0-…?cas=4407               → 4414  state done, ответ 201

── создание камеры 2 (T+1.2) ─────────────────────────────────────── (3.5)
OP   POST /cameras  Idempotency-Key: c1a9f742-…              → 201  id 2, worker null
con  GET  /v1/var/domain/…  ×12                              → 404
con  PUT  /v1/var/vms/idem/c1a9f742-…?cas=0                  → 4415
con  GET  /v1/var/vms/next_id                                → n 1, ModifyIndex 4405
con  PUT  /v1/var/vms/next_id?cas=4405                       → 4418  n 2
con  PUT  /v1/var/vms/idem/c1a9f742-…?cas=4415               → 4419  id "2"
con  GET  /v1/vars?prefix=vms/cameras/                       → [vms/cameras/1]
con  GET  /v1/var/vms/cameras/1                              → source и ref не совпадают
con  PUT  /v1/var/vms/cameras/2?cas=0                        → 4421
con  GET  /v1/var/vms/retention/2                            → 404
con  GET  /v1/var/vms/alarms_retention/2                     → 404
con  PUT  /v1/var/vms/idem/c1a9f742-…?cas=4419               → 4423  state done

── создание камеры 3 (T+2.0) ─────────────────────────────────────── (3.5)
OP   POST /cameras  Idempotency-Key: 2d7c6b18-…              → 201  id 3, worker null
     те же запросы, что у камеры 2; проверка источника читает две строки,
     vms/cameras/1 и vms/cameras/2; строка камеры 3 ложится с индексом 4433

── проход контроллера (T+3.4): 395 чтений, 10 записей ─────────────── (4.1–4.6)
ctl  GET  /v1/vars?prefix=vms/placement/   ×2                → []   unplace_deleted, unplace_retired
ctl  GET  /v1/vars?prefix=vms/workers/                       → []   sync_assignments…
ctl  GET  /v1/vars?prefix=vms/placement/                     → []   …и решений сверять не с чем
ctl  GET  /v1/vars?prefix=vms/cameras/                       → 3 пути
ctl  GET  /v1/var/vms/cameras/1..3                           → 3 строки
     камера 1:
ctl  GET  /v1/var/vms/placement/1                            → 404  решения нет
ctl  GET  /v1/var/vms/cameras/1                              → та же строка
ctl  GET  /v1/vars?prefix=objects/vms/heartbeats/ + w-1..3   → живые: server, labels, capacity
ctl  GET  /v1/vars?prefix=vms/slots/ + w-1..3                → released false
ctl  GET  heartbeat'ы воркеров + /v1/vars?prefix=objects/platform/resources/ + srv-1..3   → live
     …эти восемь запросов трижды, по разу на воркера
ctl  GET  /v1/var/vms/policy                                 → 404  shared
ctl  GET  /v1/var/platform/drain                             → 404  никого не выводят
ctl  GET  heartbeat'ы воркеров (листинг и три объекта)  ×6   метки и сервер каждого (eligible)
ctl  GET  /v1/vars?prefix=vms/cameras/ + 1..3                → соседи по прибору: нет
ctl  GET  /v1/vars?prefix=objects/rec/heartbeats/            → []   записи нет — дома нет
ctl  GET  heartbeat'ы воркеров, затем /v1/var/vms/workers/w-1   → 404  load 0
     …то же для w-2 и w-3
ctl  GET  heartbeat'ы воркеров ×2 и ресурсов ×1              → сервер победителя и его ресурс, для reason
ctl  GET  /v1/var/vms/placement/1                            → 404
ctl  PUT  /v1/var/vms/placement/1?cas=0                      → 4441  w-1 + reason
ctl  GET  /v1/var/vms/workers/w-1                            → 404
ctl  PUT  /v1/var/vms/workers/w-1?cas=0                      → 4444  units "1", rev 1
     камеры 2 и 3: те же чтения (у w-1 теперь load 1, потом у w-2 тоже)
ctl  PUT  /v1/var/vms/placement/2?cas=0                      → 4449  w-2
ctl  PUT  /v1/var/vms/workers/w-2?cas=0                      → 4452  units "2"
ctl  PUT  /v1/var/vms/placement/3?cas=0                      → 4457  w-3
ctl  PUT  /v1/var/vms/workers/w-3?cas=0                      → 4460  units "3"
     redistribute — 41 чтение, ни одной записи:
ctl  GET  /v1/vars?prefix=vms/placement/ и по каждой строке: placement/N, cameras/N
ctl  GET  heartbeat'ы, слоты, по воркеру — его сервер и ресурс, platform/drain, vms/policy
     ensure_home(1) — 44 чтения, ни одной записи:
ctl  GET  пул заново (те же чтения, что в 4.1), листинг камер,
          и на каждую камеру: /v1/vars?prefix=objects/rec/heartbeats/ → [], placement/N
     publish_snapshot — 20 чтений, 4 записи (T+3.7):
ctl  GET  /v1/vars?prefix=vms/cameras/ + 1..3
ctl  GET  /v1/var/vms/placement/N + heartbeat'ы воркеров     → сервер каждой камеры, ×3
ctl  GET  /v1/vars?prefix=objects/vms/snapshot/              → [unplaced]
ctl  PUT  /v1/var/objects/vms/snapshot/w-1..3                → по шарду на воркера
ctl  PUT  /v1/var/objects/vms/snapshot/unplaced              → снова пустой

── воркеры забирают камеры (T+4.1 … T+5.0) ───────────────────────── (5.1–5.3)
w-1  GET  /v1/var/vms/workers/w-1                            → units "1", rev 1, ModifyIndex 4444
w-1  GET  /v1/var/vms/cameras/1                              → revision 1
w-1  GET  /v1/var/vms/epoch/1                                → 404  эпохи нет
w-1  PUT  /v1/var/vms/epoch/1?cas=0                          → 4463  epoch 1
     пайплайн: ни одного запроса к хранилищу
     …то же на w-2 (камера 2) и w-3 (камера 3)
w-1  GET  /v1/vars?prefix=vms/requests/                      → []   заявок нет: каждые 0,25 с
w-1  GET  /v1/vars?prefix=objects/vms/commands/              → []   уборка отметок, раз в 30 с

── продление слота и аренд (примерно раз в 10 с) ─────────────────── (5.2, 8.6)
w-1  GET  /v1/var/platform/schema                            → 404
w-1  GET  /v1/var/vms/slots/w-1                              → holder — я
w-1  PUT  /v1/var/vms/slots/w-1?cas=…                        → until +45
w-1  GET  /v1/var/vms/epoch/1                                → epoch 1 — мой
     …то же на w-2 и w-3

── отчёт (T+10.3) ────────────────────────────────────────────────── (5.4)
w-1  PUT  /v1/var/objects/vms/heartbeats/w-1                 → 4466  running, observed_revision 1, headroom 49
     …то же на w-2 и w-3

── подтверждение (T+12.0) ────────────────────────────────────────── (6.1–6.4)
OP   GET  /cameras                                           → rows 3 × running, configured 3
con  GET  /v1/var/domain/…  ×12                              → 404  ворота
con  GET  /v1/vars?prefix=objects/vms/heartbeats/ + w-1..3   → фактическое
con  GET  /v1/vars?prefix=vms/cameras/ + 1..3                → желаемое
con  GET  /v1/var/domain/…  ×6                               → 404  фильтр по правам: всего 26 чтений
OP   GET  /where/1                                           → w-1 + reason, directory w-1
con  GET  /v1/var/domain/…  ×6, /v1/var/vms/cameras/1, /v1/var/domain/…  ×6
con  GET  /v1/var/vms/placement/1                            → worker, reason
con  GET  /v1/vars?prefix=vms/workers/ + w-1..3              → directory: всего 18 чтений
OP   GET  /metrics                                           → vms_cameras_running 3
con  GET  heartbeat'ы воркеров ×7, ресурсов ×1, шарды снапшота (листинг и четыре),
          /v1/var/objects/vms/controller/pass → 404          → ворот нет: всего 38 чтений
dom  GET  /v1/vars?prefix=objects/vms/snapshot/ + unplaced, w-1..3   (слой над кластером, если он есть)

── правка камеры 2 (после T+12.0) ────────────────────────────────── (7.1)
OP   PUT  /cameras/2  Idempotency-Key: 3f9c1e2a-…            → 200  revision 2
con  GET  /v1/var/domain/…  ×6, /v1/var/vms/cameras/2, /v1/var/domain/…  ×6
con  GET  /v1/var/vms/cameras/2   ×4                         → admit_cams: строка до и после правки
con  PUT  /v1/var/vms/idem/3f9c1e2a-…?cas=0                  → 5130
con  GET  /v1/var/vms/cameras/2                              → ModifyIndex 4421
con  PUT  /v1/var/vms/cameras/2?cas=4421                     → 5133  revision 1→2
con  PUT  /v1/var/vms/idem/3f9c1e2a-…?cas=5130               → 5135  state done
w-2  GET  /v1/var/vms/workers/w-2                            → units "2"
w-2  GET  /v1/var/vms/cameras/2                              → revision 2 → перезапуск под той же эпохой
w-2  PUT  /v1/var/objects/vms/heartbeats/w-2                 → observed_revision 2

── удаление камеры 2 ─────────────────────────────────────────────── (7.2)
OP   DELETE /cameras/2                                       → 200  deleted 2
con  GET  /v1/var/domain/…  ×12 и /v1/var/vms/cameras/2  ×5  → ворота, как у правки
con  GET  /v1/var/vms/cameras/2                              → есть и не помечена
con  GET  /v1/var/vms/cameras/2                              → ModifyIndex 5133
con  PUT  /v1/var/vms/cameras/2?cas=5133                     → 5140  deleted true
con  GET  /v1/var/vms/retention/2                            → 404  срок не задавали
con  PUT  /v1/var/vms/retention/2?cas=0                      → 5142  days 0 — пишется и без строки
w-2  GET  /v1/var/vms/workers/w-2                            → units "2"  (ещё называет её)
w-2  GET  /v1/var/vms/cameras/2                              → deleted → пайплайн гаснет
w-2  PUT  /v1/var/objects/vms/heartbeats/w-2                 → status [], headroom 50
ctl  GET  /v1/vars?prefix=vms/placement/ и по строке: placement/N, cameras/N   → у второй пометка
ctl  GET  /v1/var/vms/workers/w-2
ctl  PUT  /v1/var/vms/workers/w-2?cas=4452                   → units "", rev 2       ← сначала
ctl  GET  /v1/var/vms/placement/2
ctl  PUT  /v1/var/vms/placement/2?cas=4449                   → worker "", reason deleted  ← потом
ctl  PUT  /v1/var/objects/vms/snapshot/w-1, w-3              → шарды
ctl  PUT  /v1/var/objects/vms/snapshot/w-2, unplaced         → пустые
```

## Отказы части 8

В основном сценарии этих запросов нет: каждый блок — то, чем отличается от него один отказ.

```
── 8.1 «Сохранить» дважды ───────────────────────────────────────────────────
con² PUT  /v1/var/vms/idem/8f4b21e0-…?cas=0                  → 409  ключ уже занят
con² GET  /v1/var/vms/idem/8f4b21e0-…                        → pending, id "1": первая ещё пишет
con² GET  /v1/var/vms/idem/8f4b21e0-…                        → done → тот же 201
     (или 409 «in flight», если первая так и не дописала)

── 8.2 два оператора на разных консолях ─────────────────────────────────────
conA GET  /v1/var/vms/next_id                                → n 1, ModifyIndex 4405
conБ GET  /v1/var/vms/next_id                                → n 1, ModifyIndex 4405
conБ PUT  /v1/var/vms/next_id?cas=4405                       → 4418  n 2
conA PUT  /v1/var/vms/next_id?cas=4405                       → 409
conA GET  /v1/var/vms/next_id                                → n 2, 4418   (после случайной паузы)
conA PUT  /v1/var/vms/next_id?cas=4418                       → 4426  n 3
conA GET  /v1/vars?prefix=vms/cameras/, cameras/1, cameras/2 → источник не занят
conA PUT  /v1/var/vms/cameras/3?cas=0

── 8.3 метка, которой нет ни на одном сервере ───────────────────────────────
OP   GET  /where/4                                           → 404  worker null
OP   GET  /unplaceable                                       → [{id 4, labels [vlan:cctv-dmz], workers_live 3}]
ctl  PUT  /v1/var/objects/vms/snapshot/unplaced              → cameras [{id 4, …}]

── 8.4 замолчал ресурс srv-2 (и 8.6 — слот w-2 отпущен) ─────────────────────
ctl  PUT  /v1/var/vms/placement/2?cas=4449                   → w-1, reason «resource on srv-2 silent…»   ← первым
ctl  PUT  /v1/var/vms/workers/w-2?cas=…                      → units ""
ctl  PUT  /v1/var/vms/workers/w-1?cas=…                      → units "1,2"

── 8.6 w-2 упал: слот просрочен ─────────────────────────────────────────────
ctl  GET  /v1/vars?prefix=vms/slots/, /v1/var/vms/slots/w-2  → until в прошлом, released false: ждать
w-2  GET  /v1/var/platform/schema                            → 404  (так выглядело продление, пока он жил)
w-2  GET  /v1/var/vms/slots/w-2                              → ModifyIndex 5120
w-2  PUT  /v1/var/vms/slots/w-2?cas=5120                     → 5121  until +45
new  GET  /v1/var/platform/schema, /v1/vars?prefix=vms/slots/, slots/w-1..w-3, slots/w-2
new  PUT  /v1/var/vms/slots/w-2?cas=5121                     → holder alloc-0099, gen 2
new  GET  /v1/var/objects/vms/heartbeats/w-2                 → прежний отчёт: отсюда меряется перерыв
new  GET  /v1/var/vms/workers/w-2, /v1/var/vms/cameras/2     → units "2": назначение унаследовано
ctl  GET  /v1/var/vms/slots/w-2                              → по слову оператора (Controller.retire, справочник)
ctl  PUT  /v1/var/vms/slots/w-2?cas=5120                     → released true — единственное изменение

── 8.7 две копии w-2 ─────────────────────────────────────────────────────────
new  PUT  /v1/var/vms/slots/w-2?cas=1011                     → holder alloc-2b, gen 2
new  GET  /v1/var/vms/workers/w-2, /v1/var/vms/cameras/2
new  GET  /v1/var/vms/epoch/2                                → epoch 1
new  PUT  /v1/var/vms/epoch/2?cas=1024                       → epoch 2
old  GET  /v1/var/platform/schema                            → 404
old  GET  /v1/var/vms/slots/w-2                              → holder alloc-2b — не я: никто (seeking), гасит всё
old  GET  /v1/var/platform/schema  ×2, /v1/vars?prefix=vms/slots/, slots/w-1..w-3
old  GET  /v1/var/vms/slots/w-4                              → 404
old  PUT  /v1/var/vms/slots/w-4?cas=0                        → holder alloc-2, gen 1
old  GET  /v1/var/vms/workers/w-4                            → 404  начинает пустым
old  PUT  /v1/var/objects/vms/heartbeats/w-4                 → was_fenced «slot w-2 is held by another instance now»
     переназначение, а не зомби: слот мой, а одна эпоха сменилась —
wrk  GET  /v1/var/vms/epoch/1, 2, 3                          → у камеры 2 эпоха 2 → гаснет только она

── 8.8 камер больше, чем ёмкости ────────────────────────────────────────────
new  PUT  /v1/var/vms/slots/w-2?cas=0                        → второй воркер, после nomad job scale
new  PUT  /v1/var/objects/vms/heartbeats/w-2                 → capacity 50, headroom 50

── 8.9 строка не читается ────────────────────────────────────────────────────
w-2  GET  /v1/var/vms/slots/w-2                              → until «завтра», ModifyIndex 1028
w-2  PUT  /v1/var/vms/slots/w-2?cas=1028                     → переписана целиком
w-2  GET  /v1/var/vms/epoch/2                                → epoch «два»
w-2  PUT  /v1/var/objects/vms/heartbeats/w-2                 → камера 2: failed, why «its epoch could not be taken…»
```

## Итог по числам

| Что | Запросов к Nomad | Из них работы |
|---|---|---|
| создание камеры 1 | 23 | 9: пять записей и четыре чтения; плюс 12 чтений ворот и 2 подчистки |
| создание камеры 2 / камеры 3 | 22 / 23 | 9 и по чтению на каждую уже заведённую камеру; подчистки нет |
| первый проход контроллера, три камеры | 395 чтений, 10 записей | 6 записей размещения и 4 шарда снапшота |
| холостой проход контроллера | 134 чтения, 4 записи | только снапшот |
| воркер поднимает камеру | 4 | назначение, строка, эпоха — чтение и запись |
| продление воркера | 3 + по чтению на камеру | одна запись — слот |
| `GET /cameras` / `/where/1` / `/metrics` | 26 / 18 / 38 | ворота — 18, 12 и 0 из них |
| правка | 21 | 4; ключ идемпотентности страница шлёт, для `PUT` он необязателен |
| удаление | 22 | 5; ключа идемпотентности нет вовсе |

Обратите внимание на асимметрию в конце: **воркер гасит видео раньше, чем контроллер тронул размещение**. Консоль только помечает строку, воркер на своём проходе её пропускает, а контроллер приходит потом и делает две записи бухгалтерии ([часть 7](07-edit-and-delete.md)). И на число чтений холостого прохода: оно растёт как `камеры × (воркеры + 16)`, потому что контроллер ничего не запоминает внутри прохода ([4.6](04-placement.md), [часть 10](10-limits-and-scale.md)).

---

[← карта разбора](README.md) · назад: [10-limits-and-scale.md](10-limits-and-scale.md)

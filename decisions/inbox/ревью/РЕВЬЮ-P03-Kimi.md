# РЕВЬЮ P/03 — production norms checklist 1–14

- Ревьювер: review103-kimi (фоновый агент, CT 103).
- Основание: задание dispatcher103 «P03 production norms checklist 1–14», полномочия ADR-0083 доп. (152) (directDispatcher), ADR-0130 (4), (5), (6) (checklist 14, порядок единиц).
- Immutable-задание: `/home/pilot/cammeta-sessions/dispatcher-tasks/2026-11-08-adr0130-p03-direct/review103-kimi-P03-TASK.json`, sha256 `f721b7c22822f2fb166c029e81e9d023a1b1ad632b0b959e8bad0a98e67ae88b` (сошёлся).
- Source pin: `244355d161139bd6fe65fd68c7e5134598c21ba3` (parent `061f004970584dd8a279b6ae9808238a1a68e3dd`), ветка `kimi103/review-p03-244355`.
- Ростер: 38 файлов `Platform/03-worker/**`, blob-хеши сверены через `git rev-parse <pin>:<path>` — 38/38 совпали.
- Режим: только чтение Source; без исполнений, нативных прогонов, моделей, сети; report-only; whole unit / READY / GATE не объявляются.

## Охват и пределы (честно)

Прочитаны целиком все 38 носителей ростера: `spec/03-worker.README.md`, `spec/03.1–03.7-worker.norms.md`, `forms/README.md`, `forms/daemon-flags.tsv`, `forms/refusals.tsv`, `forms/row-write-bindings.md(+tsv)`, `forms/runtime-constants.tsv`, `forms/slot-capture.tsv`, `forms/stages.tsv`, `forms/contender-writer.machine.yaml(+traces.tsv)`, `forms/token-cache.machine.yaml(+traces.tsv)`, `acceptance/1,5,7/README.md+seams.tsv`, `acceptance/2,3,4,6/README.md+scenarios.tsv+seams.tsv`.

Точечные внешние ссылки — только по фактическому обращению носителей: `common/contracts/env-file.md` (FOR=300, WatchdogSec=360), `common/contracts/slot.md` (SLOT_TERM=45, TORN_MARGIN=5, TORN_STILL=50), `common/contracts/observation.md` (LOST_AFTER=45, HOLD_SKEW=5, CONTENDER_FRESH=300), `common/contracts/request-mark.md` (kept=max(60, ttl); limits fetched), `common/contracts/store-client.md` (wait), `common/contracts/presence-lock.md`, `common/contracts/event-journal.md`, `Platform/01-store/spec/01.1-store.norms.md` (id/ambiguous/replay), `Platform/02-installer/spec/02.1-installer.norms.md` (worker.stop_timeout 20…50), `Platform/06-console/spec/06.4-console.norms.md` (FETCHED_* → 03.6).

Пределы: (1) peer-отчёты (P02 и любые другие) и прежние отчёты/архивы не читались; common-находки по ADR-0130 (10) не пересчитывались — владельцам; (2) family-read 5/15 не трактовался как автоматический дефект нормы (предел задания); (3) прогоны/стенды/модели не исполнялись — статус «проба» ниже означает наличие/отсутствие носителя пробы (сценарий TSV, SDK-шов, векторы, следы машины) в ростере, а не выполненный прогон; (4) код реализации (`Source/`), судьи и генераторы вне охвата; (5) числа норм сверялись между собой (константы, формулы, сценарные арифметики, следы машин) — новых чисел не вводилось.

## Опорные константы единицы (подтверждены перекрёстно)

Окно lease 25 s = LEASE_TTL 30 − LEASE_MARGIN 5; LEASE_EVERY = 25/3 ≈ 8.3 s; STALL = 12.5 s; WAKE ≤ 6.25 s; FOR = 300 s (границы в швах acceptance/4: 12.5/12.501, 300/300.001); BEAT_EVERY = 10 s; HEARTBEAT_EVERY = 10 s; CONTEND_EVERY = 10 s; WAKE_GAP = 0.25 s; PASS_SHARE = 2; RETRY_MIN 1 s, RETRY_MAX 60 s; SLOT_TERM = 45 s, TORN_STILL = 50 s; LOST_AFTER = 45 s, HOLD_SKEW = 5 s (LOST_AFTER + HOLD_SKEW = 50; «at — already free»); CONTENDER_FRESH = 300 s; WRITE_WINDOW = 40 s, CLOSE_BY = 50 s; strict place 40/50 (checklist P/03.2-12); бюджет закрытия мест после SIGTERM ≥ WRITE_WINDOW − RENEW_EVERY ≈ 31 с; дверь процесса: 32 conn / 8 per address / заголовки 5 s / pace 65536 B/s после 30 s / тело 1048576 B / busy 503 Retry-After 1; holder: PERFORM_TIMEOUT 10 s + PERFORM_GRACE 0.2 s, REQUESTS_HOLD 0.5 s, COMMANDS_PER_LOOK 200; STATE_EVERY 10 s; MADE_ROWS_MIN_INTERVAL 60 s; COMMAND_BEHIND_TOLERANCE 1 s (строгое «больше»); gen/epoch граница 2^53−1 (ровно max — generation_exhausted / refusal issue, без записи); worker.stop_timeout 20…50, default 20; unconfirmed_max: off (default) | forever | ≥1 s.

## Матрица 14 пунктов × части единицы

Статусы: **ОК** = нормативный якорь + носитель пробы; **Н** = норма есть, пробы нет (finding ниже); **МВ** = missing-input finding (бюджёт отсутствует, disposition — «конечный бюджет, объявленный реализацией» + проба среды); **Н/П** = неприменимо с причиной.

| # | Боевое свойство | Носители-якоря (норма) | Проба | Статус |
|---|---|---|---|---|
| 1 | Лимиты соединений/запросов | 03.4 N1.7 door_limits + runtime-constants (32/8/5 s/64 KiB/30 s/1 MiB) + refusals.tsv 3.4/5–7 + checklist P/03.4-11 | нет (стенд без двери подсистемы) | Н → М1 |
| 2 | Read/idle timeouts, drain | дверь: HEAD_WITHIN 5 s, PACE_AFTER 30 s; store-client `wait` — implementation decides; drain: pending_writes (03.4 N1.1; «нет поля — drain not safe», владелец P/06.6); закрытие suppression-окон до последнего heartbeat (C03-SUPPRESS-STOP-01); порядок stop (03.4 N3) | шов s1-stop-order; sc. 24 (молчание 10 s); s5/s6 heartbeat-base (pending_writes 0) | частично; дверь → М1, drain-переход → М2 |
| 3 | Ожидание блокировок | слот: non-blocking (stand-in пропускает; 03.4 N3 Races); presence lock: blocking flock без LOCK_NB (presence-lock.md; P/03.2-13 гонка open/flock — чтением); store lock wait → `unavailable` (P/01.1, impl decides) | нет | Н → М3 |
| 4 | Barrier / write failure / ambiguous | 03.4-07: каждый write с id, после ambiguous — replay тем же id; take_epoch: not confirmed → retry same id, повторно не подтверждён → refusal (03.2 N3); order: 9. unavailable/ambiguous → same write id (03.6 N3); slot-capture: reply unconfirmed → wait() тем же id, definite refusal → reject | швы s11-capture-replay, s18-guard-own-renewal; R29-cases (README acceptance/2) | ОК; узкая ветка → М4 |
| 5 | Эксклюзив: каталог данных/адрес/лидерство | presence lock файл на инстанс (03.2 start 2b); имя — один holder через cas (03.2 N3 capture/races); domain worker — один активный по слоту (03.7 N1.6); exclusive place (03.2 N3 place, affinity.exclusive); адрес двери: kit → адреса SERVER_NAME, иной `<DOOR>_HOST` → code 2 (03.4-12) | sc. 04/29 (две копии), sc. 08 (два манифеста), швы s3–s7 (capture), sc. 09/6 (место до assignment) | ОК; exclusive place/secret → М5 |
| 6 | Стоимость записи / импорт: объём и растущие состояния | единицы объёма: строка события (append + fsync alarm/journal), heartbeat-объект (10 s), contender object (10 s при due), слот 2 записи + cleanup, epoch/holds/state/marks/contribution строки; растущие: suppress-окна по (tree, unit, epoch, kind, class), счётчики uint53, histograms (ровно 10 бакетов), fetched (FETCHED_COUNT/BYTES — 03.6 impl.decides 1), command_* по множеству filer, made_rows по customer, epoch rows не удаляются (граница 2^53−1, refusal до записи) | sc. 13 (нулевые счётчики), sc. 18 (граница epoch), швы s19–s22 (gen), s5 heartbeat-base | ОК по границам; бюджёт размера heartbeat → С2; suppress-пробы → М6 |
| 7 | Framing | дверь: неполная строка/заголовки за 5 s → разрыв; тело > 1 MiB → 413 до чтения; строка события целиком под LOCK_EX (event-journal.md); heartbeat/семейства — JSON Schema 2020-12 | нет (дверь), шов s2-crash (не про framing) | Н → М1 (общая причина с п. 1/2) |
| 8 | Backup / export / incomplete | восстановление хранилища поднимает epoch_floor; epoch < floor → lost, процессы не перезапускаются (03.2 N3/Races); floor не читается → refusal issue, 0 не подставляется; keep-токен: файл 0600 в envelope (03.7 N1.5), предел «кража коробки даёт токен до отзыва»; witness object | sc. 26/27 (floor, spoil), швы s13, s27–s30; s2/s4 token | ОК по P/03-части; импорт/restore строк — владелец P/01.3 (не дублирую) |
| 9 | Restart / orderly stop: дедлайн, cancel, admitted work, освобождение ресурсов, восстановление | SIGTERM 5 шагов (03.4 N3): stand-in → before_stop_all → stop units → close place writers → last heartbeat → let go place → release slot → after_stop; crash молча; worker.stop_timeout 20…50 (P/02.1); fencing отменяет accepted-but-unfinished starts (03.2-R045); rejoin/name_back; окна подавления закрываются под may_write | швы s1-stop-order, s2-crash-no-hooks, s15-gate-cancelled-late-start; sc. 03/05/37; sc. 29 (возврат имени) | ОК по порядку/cancel; дедлайн фактической остановки → М8 |
| 10 | RAM / disk / fd / units | RAM: CAPACITY×unit_mb + base_mb ≤ WORKER_MEMORY_MB, иначе не старт (03.4 N1.2; MemoryBudgetRefused); units: capacity/headroom по весам (weight 1 default, не-число — не в сумме); fd: только косвенно через дверь 32/8; disk: event trees append-only, retention — владелец P/05 | швы s3-budget-domain-no-role, s4-budget-over; headroom — чтением (N5) | RAM ОК; fd/disk бюджёт отсутствует → С1 |
| 11 | Очереди / backpressure | дверь: busy 503, очереди нет, Retry-After 1; группа команд: пока вызов в группу не вернулся, младшие ждут (порядок по at/rid); holder look ≤ REQUESTS_HOLD 0.5 s, ≤ COMMANDS_PER_LOOK 200; цикл: WAKE_GAP 0.25 s, PASS_SHARE 2; contender — публикация только when due | шов s4-group-busy-after-timeout (max_unfinished 1); пробы удержания look нет | частично; look-дедлайн → М9; дверь → М1 |
| 12 | Недоступность зависимостей | store молчит: renew → still mine, lease silent → unconfirmed_max (off/конечный/forever), «data go on, commands wait»; quorum 2/3 → 503 после 5 s (system stand, чтением); schema read error → continue; decommission row не читается → no name until readable; resource heartbeat не читается → relieve не считается (владелец P/05); domain silent → keep-файл токена | sc. 24 (тишина 10 s), шов s1-capture-unknown; token s2/s4 | ОК; agent door для keep:false → М10 |
| 13 | Скачки/скew часов | monotonic для lease/слота/observation; wall — только until/ts на дисплей (ADR-0049); свой срок записи от отправки подтверждённого renew; сдвиг часов писателя не продлевает удержание; since переживает откат часов (contender trace); срок токена судит получатель, не локальные часы (03.7-R009); HOLD_SKEW 5, TORN_MARGIN 5, COMMAND_BEHIND_TOLERANCE 1 (строго больше) | traces contender-writer; token-cache s4-keep-current-local-exp + keep-current probe; sc. 44 (unreadable heartbeat ≠ not fresh); run 25 (слот-дедлайны — чтением) | ОК |
| 14 | Повторы / шторм | backoff 1…60 s с обязательным jitter, считаются только фейлы старта/работы, сброс на трёх условиях, stalled; replay тем же id без движения t0; запрет blind retry по 412 guard; late answer не оживляет попытку; publish contender только when due; heartbeat stand-in не чаще BEAT_EVERY; same-JTI → ожидание до конца дня; unknown_key по current → wait, не запрос; плохой rid → refused без ступора | швы s4-backoff-confirmed-absence, s16-confirm-overslept, s17-confirm-last-monotonic; token traces; s12-epoch-initial-late | ОК; исчерпание cas-лимита → М11 |

## Findings

Типы: contradiction / new meaning / missing normative input / proposal. Противоречий (норма против нормы, норма против формы, форма против следа) не найдено: числовые константы, формулы окн, сценарные арифметики (25−8.3≈16.7; 12+50=62; 3×100+10>309; 1+10.2=11.2; 1000+720=1720; границы 2^53−1; floor 2^32/2^33) и следы обеих машин согласованы с нормами; формы заявляют и подтверждают «existing norms, no new API» (ADR-0125 доп. (5)) — новых смыслов не введено. Findings ниже — missing-input и proposal, по одной причине на находку.

### С (существенные)

**С1 — missing normative input, п. 10 (fd/disk).** Конечный бюджёт файловых дескрипторов и диска процесса воркера нигде в единице не объявлен: RAM покрыта формулой бюджёта (03.4 N1.2), дверь косвенно ограничивает сокеты (32/8), но fd (lock-файлы, журналы, сокеты агента) и рост event trees/objects (append-only, `retention` — владелец P/05) без конечного числа. Disposition: «конечный бюджёт, объявленный реализацией» + проба среды (fd/диск под нагрузкой); без новых чисел. Владелец common-fixes: retention — P/05 (owner pending, не дублирую).

**С2 — missing normative input, п. 6/10 (размер heartbeat-объекта).** Растущие поля heartbeat не имеют конечного бюджёта размера: `fetched` ограничен FETCHED_COUNT/FETCHED_BYTES, но значения — «Implementation decides» 03.6 п. 1 без числа; `command_road`/`command_request` — ключи по открытому множеству filer (`by` — operator или подсистема), `made_rows` — по customer-префиксам; счётчики/histogram — uint53 (конечны, но не бюджёт размера). Disposition: «конечный бюджёт, объявленный реализацией» + проба среды (размер объекта под нагрузкой); без новых чисел.

### М (мелкие / предложения пробы)

**М1 — proposal, п. 1/2/7 (процессная дверь).** Нормы двери с числами есть (03.4 N1.7, constants, refusals 3.4/5–7, checklist P/03.4-11/12), но ни один из 38 носителей не исполняет дверь: 03.4 N5 прямо — «the stand has no subsystem process with a door», проверка — «by reading and by a test of the door server of the implementation» (долг ADR-0091 доп. (7)–(9); TLS-стенд несёт domain doors, не дверь реализации). Одна находка на три пункта — общая причина.

**М2 — proposal, п. 2 (drain).** Переход в безопасный drain («no pending_writes — the drain is not safe») — норма владельца P/06.6 N1.2; P/03 лишь пишет pending_writes := 0 (шов s5/s6 проверяет значение, не переход drain). Проба отсутствует; owner pending по common-fixes, не дублирую.

**М3 — proposal, п. 3 (ожидания блокировок).** Гонка «останов между open и flock» presence lock назначена чтением (checklist P/03.2-13; review of stage B 3–5 № 19) — носителя пробы нет; store lock wait → `unavailable` — норма владельца P/01.1 (impl decides). Блокирующий flock без дедлайна — явное решение контракта presence-lock.md, дефектом не считаю.

**М4 — proposal, п. 4 (ветка отказа issue).** «Outcome not confirmed → retry same id; not confirmed even then — a refusal, do not hand out a new lease» (03.2 N3 take_epoch) не имеет пробы двойного неподтверждения: s11 покрывает replay с успехом, s12 — поздний ответ, исход «refusal после повторного неподтверждения» без носителя.

**М5 — proposal, п. 5 (exclusive place / secret места).** Нормы есть (03.2 N3 place: exclusive берётся только воркером без мест и юнитов; 03.5 N3: Sealed места → не взять/leave_place, place_error), пробы нет — долги ADR-0091 доп. (9)–(10), P/03.5-03, P/03.2-17 («when a teaching subsystem gets such a place (debt)»).

**М6 — proposal, п. 6 (suppression).** Нормы подавления (окно, by, summary, закрытие при stop под may_write перед последним heartbeat — C03-SUPPRESS-SUMMARY-01/STOP-01) есть; пробы нет ни в одном носителе (03.6 N5: «the acceptance of P/02.1 has no cases of suppress; the stand does not write repeats» — checked by reading).

**М7 — proposal, п. 8 (keep-файл токена).** `persist` в token-cache — IO intent, не подтверждение записи; фактический файл (`<state dir>/tokens/<kind>-<sha16(ref)>`, mode 0600, envelope с контекстом пути, «envelope did not open — as if there were no file») носителем не проверен (seam s1 лишь file_writes=0 для keep:false).

**М8 — proposal, п. 9 (дедлайн остановки).** worker.stop_timeout 20…50 (default 20) и бюджёт закрытия мест ≥ WRITE_WINDOW − RENEW_EVERY (40 − 8.3 ≈ 31 с) — нормы есть; проба фактического времени SIGTERM → exit и удержания дедлайна нет (шов s1-stop-order проверяет порядок happens-before, не время; sc. 03/37 — факт release, не дедлайн).

**М9 — proposal, п. 11 (удержания holder look).** REQUESTS_HOLD = 0.5 s и COMMANDS_PER_LOOK = 200 — нормы есть; швы worker-holder-look/группа проверяют логику, а не отсечение по удержанию/лимиту за look.

**М10 — proposal, п. 12 (agent door для keep:false).** Недоступность локальной двери агента / молчание домена для вида без keep — пробы нет (refusals двери — владелец 9.1; keep-путь покрыт s2/s4 и machine/traces).

**М11 — proposal, п. 14 (исчерпание cas-ретраев).** Лимиты повторов `conflict` при capture/epoch/issue и число cas-ретраев renew — «Implementation decides» с нормированным исходом исчерпания (refusal попытки / refusal order); пробы исхода исчерпания нет.

## Сводка

- Блокеры (Б): **0** — невыполнимости нет; расхождений норм с контрпримерами не найдено.
- Существенные (С): **2** (С1, С2 — missing normative input с disposition «конечный бюджёт, объявленный реализацией» + проба среды, без новых чисел).
- Мелкие (М): **11** (М1–М11 — предложения носителей проб; все причины различны, дубли с common-fixes ADR-0130 (10) сняты ссылками на владельцев).
- Итого findings: 13 (≤ 40). Контрадикций: 0. Новых смыслов: 0.

Подпись: review103-kimi, 2026-11-08 (UTC), CT 103. Отчёт — normal child точного пина 244355d161139bd6fe65fd68c7e5134598c21ba3; whole unit / READY / GATE не объявляются.

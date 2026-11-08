# РЕВЬЮ P/04 — production norms checklist 1–14 — Kimi (review103-kimi)

- Основание: задание Диспетчера `review103-kimi-P04-959AF8-TASK.json` (sha256
  `b45bfafd7847385b3e724f7620f0987a402c07dcc4866d009a139a9c1cbbc70e`), authority ADR0083(152)directDispatcher,
  ADR0130(4),(5),(6)checklist14/unitorder.
- Source pin: `959af8d62e7c35ab527fde6e86979b1279ead2ba` (поле `Sourcepin` задания; ветка
  `kimi103/review-p04-959af8d6`). Внутри текста `review_scope` задания осталась шаблонная строка
  «Source pin 244355…» — по `scope_note` задания старые 244-P04-шаблоны неактивны, назначен published Source
  959af8d6; расхождение зафиксировано здесь одной фразой, находкой не является.
- Сверка ростера: все 12 blob-хешей `primary_public_roster` совпали с `git hash-object` на пине.
- Характер работы: только чтение Source на пине. Без исполнений, нативных прогонов, моделей, сети (кроме
  git fetch/push служебного клона). Peer-исходы P01–P03, прежние отчёты и архивы не читались. Quint не строился.
  Whole unit / READY / GATE не объявляются.

## Охват и пределы

- Прочитан целиком ростер из 12 файлов: `Platform/04-controller/spec/04-controller.README.md`,
  `spec/04-controller.norms.md` (1541 строка), `acceptance/README.md`, `acceptance/scenarios.tsv` (562 строки),
  `acceptance/seams.tsv` (67 строк, включая все s1–s63), `forms/README.md`, `forms/daemon-flags.tsv`,
  `forms/runtime-constants.tsv`, `forms/refusals.tsv`, `forms/stages.tsv`, `forms/slot-fate.tsv`,
  `forms/slot-release.tsv`.
- Точечно по фактическим ссылкам ростера: `common/contracts/production-obligations.md` (ADR-0130(10), Q1–Q6,
  MB1–MB4), `common/contracts/turn.md` (Terms/Barrier/Production obligations), `common/contracts/store-client.md`
  (Answer/Outcomes/Q4/wait), `common/contracts/object-client.md` (Address/door/Outcomes/Q1),
  `common/contracts/observation.md` (Freshness/Resource state), `common/vectors/production-obligations/README.md`,
  `Platform/04-controller/lifecycle.md` (связан из колонки norm daemon-flags.tsv).
- Пределы: (а) common-пробелы ADR-0130(10) (исполняемые биндинги Q1–Q6/MB1–MB4, owner-native пробы clock/capacity,
  MissingBinding/NOTEXEC) — владение common/Runner, по заданию не пересчитывались и здесь не дублируются как находки;
  (б) смысл `rebalance.dead_band` уважен — поведение ordinary placement из него не выводилось (в реестре dead_band
  нормирован только как «rebalancing on request», см. N1.3 и «Implementation decides» п. 5); (в) хвосты
  зависимостей P/01 (BATCH_WRITES, ROW_CEILING, KEY_BYTES, replay retention), P/05 (door limit L, max_bytes,
  Content-Length), P/02.4 (workers script, memory check), P/03.2/P/03.4 (leases, SIGTERM остановки воркера) —
  владельцы соответствующих частей, оценивались только как якоря/пробы P/04.

## Матрица 14 пунктов × части P/04

Статусы: ✅ якорь+проба · ⚠ missing-input с disposition · ➖ неприменимо с причиной.

1. **conn/request — ➖.** Своей HTTP-двери нет (N2 «P/04 no-openapi»; `refusals.tsv` — поверхности `start|call|peer`,
   `peer` — двери консоли). Запросы контроллера — store client (P/01.1, сокет роли) и object door (P/05);
   лимиты соединений/запросов нормируются владельцами дверей (P/01.1 503 «connection limit» → повтор на следующем
   шаге, `store-client.md` Outcomes). Для call-процедур (seams) сеть отсутствует по построению — неприменимо.
2. **read/idle timeouts, drain — ✅.** Якоря: `store-client.md` `wait` (answer read limit и answer wait term —
   **конечный бюджет объявляет реализация**, disposition без новых чисел; `no_reply` → unavailable/ambiguous),
   `object-client.md` `door` («unknown», не «absent», без resource на сервере; P03-OBJECTS-DEFAULT-1FD), drain
   сервера — N1.1 `platform/drain` + N3 «drain» (sc.33). Пробы среды: sc.25 (`@cut/@mend role … store` — молчание
   на чтении схемы, контроллер ждёт, не стартуя), seams s26/s61 (snapshot read unavailable → 0 записей, нет пустой
   замены), s19/s45 (ambiguous/lost reply). Drain/останов самого процесса контроллера — см. находку Н1.
3. **lock wait — ✅ (с мелкой прорехой Н6).** Якоря: `turn.md` Terms (TURN_TERM 45 / TURN_RENEW 10), norms N3 step 0
   «busy → no changing pass, a retry after TURN_BUSY_RETRY», `runtime-constants.tsv` TURN_BUSY_RETRY=5 s;
   «a vanished holder delays changes at most until the next successful attempt after the observation window».
   Пробы: turn-векторы (busy-ветка, common-владелец), seams s17 (два holder'а), sc.20 (turn бывшего holder'а
   ждёт TURN_TERM 45 s), s19 (foreign_holder barrier).
4. **barrier / write failure / ambiguous — ✅.** Якоря: `turn.md` Barrier (любой non-answer/unknown/conflict/412
   прерывает план; сначала barrier своей версии turn; non-answer самого barrier запрещает продолжение; нельзя
   подставить новый guard в старую команду), `store-client.md` `ambiguous` → повтор только с тем же `id`,
   `slot-release.tsv` классы reply (pending/unconfirmed ждут, permission не публикуется), N1.4
   WRITE_CONFLICT_LIMIT=10 «after the limit the existing step fails, not an extra attempt; barriers remain».
   Пробы: seams s19 (ambiguous + barrier foreign_holder → 0 записей после), s54/s55 (точный лимит: 9 конфликтов +
   успех = 10 попыток; 10 конфликтов → шаг упал, 11-го ответа нет), `refusals.tsv` строки 8 и 13, чтение R36-04
   (barrier после non-answer, повтор без подмены guard).
5. **exclusive data dir / address / leadership — ✅ / ➖ / ⚠.** Leadership: ✅ якорь+проба — N1.5/N3 (один
   контроллер на подсистему в каждый момент, право строкой `placement_turn`, поздние записи старого holder'а
   режутся guard 412; MB4-вектор называет P/04); пробы: seams s17/s19, чтением N5 (два контроллера, паузы после
   каждого чтения/записи). Data dir/address: ➖ — своего каталога у контроллера нет: объекты — каталог сервера
   P/05 (`object-client.md` `writer`: one directory — one writer), корни создаёт роль старта (lifecycle «Stand
   without root»); адрес `$OBJECTS/$PLATFORM_OBJECTS` — форма daemon-flags + `object-client.md` Address.
   Внешние эффекты: ⚠ missing-input с disposition «owner-declared independent fence» — `turn.md` Production
   obligations (MB4): turn lease не fence для внешних эффектов; у контроллера внешних действий почти нет
   (процессы не стартует, ADR-0021), без биндинга — MissingBinding/NOTEXEC (common-владелец, не дублирую).
6. **write cost / volume unit / growing — ✅ (мелкая находка Н3).** Якоря: N1.3a `ceiling` (байты полного
   сериализованного объекта с envelope и ts; exactly L allowed, L+1 → отказ до put_durable; диагностика
   «N units on <shard>; snapshot is B bytes, limit is L bytes»), N1.3b SNAPSHOT_TABLE_MAX=1048576 bytes → stub
   `too_large`, decommission — BATCH_WRITES−1/BATCH_GUARDS/потолок тела (`all_batches_within_limits`), N1.2
   `short[].units` — точные целые без потолка uint53. Единицы объёма названы: bytes (объекты), row weights
   (батчи), slots/books (decommission), вес ожидающих (растёт с очередью). Пробы: seams s27/s28/s29 (границы
   67108864/67108865 и store TooLarge), s30/s31 (таблица 1048577, unchanged ts), s41 (65 contributions), s20
   (key limit), s51–s53 (2^53±1 точность). Новых чисел в отчёте нет — все размеры из фикстур реестра.
7. **framing — ➖.** Своего протокола нет; framing/тело — владельцы форм: P/01.1 body read limit
   (`-max-body`), P/05 Content-Length.maximum, закрытые формы ответов (`store-client.md` `forms`), объекты —
   whole-or-not-at-all (`object-client.md` `rule`). П/04 только сериализует JSON-объекты под чужие потолки.
8. **backup / export / incomplete — ✅.** Якоря: N3 «snapshot» Races — «a snapshot is an observed configuration,
   not a consistent backup»; «an unknown outcome of a write does not prove that the shard stayed the former one»;
   N1.4a power_pull (stays/lost: RPO длины бакета допустим только с подтверждённым зеркалом закрытых; restore —
   P/05 Bucket restore). Пробы: seams s26 (read unavailable → former kept, `empty_replacement:false`),
   s61 (`unchecked_empty_publications:0`), s63 (readback видит persisted bytes), acceptance README «Snapshot
   outside TSV» (max_bytes=0, <, =, > L; отказ держит прежний объект и время).
9. **restart/stop: deadline/cancel/admitted work/resource release/recovery — ⚠ (находка Н1) + ✅ по recovery.**
   Restart/recovery: ✅ — sc.20 (решение прочитано, не пересмотрено; turn бывшего holder'а ждёт TURN_TERM;
   @until 90), seams s42–s45 (resume pending после обрыва/рестарта, новый holder, отказ финала, потерянный
   ответ), P/04-24 (счётчики delete_after/retire после рестарта заново; `state_swept_total` с нуля в процессе),
   восстановление intent новым holder'ом (sc.28, шаг 3), schema check at start (sc.23/25), lifecycle
   (SIGTERM — orderly exit; SIGKILL — «the state is only in the rows»; watchdog WATCHDOG=1 на каждом проходе).
   Deadline/cancel admitted work и освобождение ресурсов при остановке: ⚠ missing-input — ни один носитель не
   называет конечный бюджет остановки/отмены (см. Н1); disposition «конечный бюджет объявляет реализация»,
   пробы среды нет.
10. **RAM / disk / fd / units — ⚠ (находка Н2).** Q5 процитирован в N0 («Q5 bounded resources also apply»), но ни
    один носитель P/04 не называет конечный бюджет памяти/диска/дескрипторов процесса контроллера и единицы
    роста его состояния (память наблюдений heartbeats/slots/resources на pass; append-журналы
    `audit/<role>/*.events.jsonl`; буферы сериализации shard). Память сервера по ролям — «a limit of the scheme
    (R12)» и memory check скрипта воркеров — владельцы P/02.4/P/03.4, не P/04. Disposition: «конечный бюджет
    объявляет реализация» (production-obligations: bytes, records, identifiers, marks, tombstones, generations,
    buckets, queued operations — как общий перечень единиц); пробы среды (saturation) в реестре нет.
11. **queues / backpressure — ✅ (мелкая прореха Н5).** Якоря: `want` — абсолютная цель, один действующий
    logical order на shortage (R2); in flight по heartbeats; withdraw on deadline WANT_GRACE=90 s; withheld →
    серия `workers_withheld{labels}` + `short[].withheld` + alarm `workers.no_server`; decommission — bounded
    chunks (BATCH_WRITES−1); TURN_BUSY_RETRY; store 503 `Retry-After`. Пробы: sc.14–17, seams s32
    (WANT_GRACE re-path), s36–s38, s51–s53, векторы order/shrink-victim/shrink-allowed, `refusals.tsv` строки
    9–12. RAISE_QUIET/RAISE_FAILS_LOUD без исполняемой пробы — Н5.
12. **dependency unavailability — ✅.** Якоря: «A silence of the store moves nothing» (N3 «leaving»); ошибка чтения
    схемы → ожидание (sc.25; lifecycle «the controller waits by itself for the readiness of the store»); без
    resource на сервере — «unknown» не «absent» (step 0, P03-OBJECTS-DEFAULT-1FD); store 503 unavailable →
    повтор на следующем шаге; power_pull store 1/3 — выборы за секунды, 2/3 — 503 после -leader-wait, воркеры
    живут по последнему assignment (lease + unconfirmed_max), восстановление вручную (P/01.3 N3). Пробы: sc.25,
    s26/s61, s45/s63, drill 05-power-pull (system acceptance), sc.12/13 (@sigkill воркера с живым resource).
13. **clock jump / skew — ✅ (пробы чтением + виртуальные часы).** Якоря: наблюдение по своим монотонным часам
    (`observation.md`: observer — own observation memory and own monotonic clock); «a shift of the writer clock
    with the same observation history does not change the fate» (N3 Races); terms считаются от первого
    наблюдения своими часами (N1.4, R039: HUNG_MOVE_AFTER не от `until` и не от `fates.since`); «a future finite
    until is not spoiling»; pitfall «judging freshness by the ts of a foreign process». Пробы: README «Checks by
    reading» (сдвиги часов писателя −30/0/+300), seams на виртуальных монотонных часах (s22, s32, s36–s38),
    sc.26/27 (@freeze/@thaw — процессная пауза). Native clock-discontinuity — owner-native roster common
    (MissingBinding/NOTEXEC), не дублирую.
14. **retries / storm — ✅.** Якоря: Q4 (ровно один владелец retry, bounded backoff/jitter, тот же `id` в пределах
    replay retention, новый id не обходит ambiguous); `turn.md` Races (повтор с тем же id не сдвигает время
    logical write); WRITE_CONFLICT_LIMIT (s54/s55); `slot-release.tsv` — no blind repeat by a newer CAS;
    decommission — never retry release against a newer version, число чтений слота после cleanup-conflict = 0
    (s43); рост ограничен: не более одного probe process на pass и на сервер (R16‴), `name_conflicts` counter.
    Пробы: seams s15 (release-cas-race → next_fate alive), s54/s55, s43; replay retention (≥2 мин/50 000) —
    владелец P/01.1 N3, не дублирую.

## Findings

Нумерация сквозная; одна причина — одна находка. Цитаты — из файлов пина.

### Н1 (С, missing normative input, п.9) — Нет конечных бюджетов остановки/отмены самого контроллера

**Место.** `Platform/04-controller/lifecycle.md` («Signals and readiness»: «**SIGTERM** — an orderly exit; an
unfinished intent is completed by the next holder of the turn» — без дедлайна и без судьбы in-flight записей);
`spec/04-controller.norms.md` N3 «pass()» (нет шага остановки), N5/P/04-02 (restart — sc.20, но не stop);
`forms/runtime-constants.tsv` (PASS_EVERY/TURN_BUSY_RETRY/… — нет ни одного бюджета shutdown/cancel).

**Почему находка.** Чек-лист п.9 требует deadline/cancel/admitted work/resource release. Реестр покрывает
crash/recovery со всех сторон: turn бывшего holder'а истекает по TURN_TERM (sc.20 ждёт @until 90), unfinished
intent достраивает следующий holder (N1.5, sc.28), decommission возобновляется из pending после обрыва (seams
s42–s45), счётчики delete_after/retire после рестарта идут заново (P/04-24), `state_swept_total` с нуля в
процессе. Но «orderly exit» не нормирует: сколько может длиться выход по SIGTERM, отменяется ли начатый
control part, дожидается ли подтверждения последняя запись turn release (step 6), какие ресурсы освобождаются
до ухода. Контрпример-асимметрия: для воркера останов по SIGTERM нормирована (P/03.4 N3 «stop by SIGTERM»,
упомянута в N1.4a/sc.14), для контроллера — нет ни нормы, ни пробы среды.

**Disposition.** `common/contracts/production-obligations.md`: «Each implementation MUST declare finite positive
budgets for … cancellation, shutdown and accepted-work completion» — конечный бюджет объявляет реализация, новых
чисел не вводится. Проба среды в реестре отсутствует; sc.20 использует `@sigterm controller` как механизм
перезапуска, а не как наблюдение остановки. Рекомендация: в lifecycle добавить строку stop-семантики
(завершение/отмена control part, turn release, граница дедлайна — по правилам владельца) и отметить пробы
среды в N5.

### Н2 (С, missing normative input, п.10) — Нет ни одного ресурсного бюджета процесса контроллера и единиц роста его состояния

**Место.** `spec/04-controller.norms.md` N0 (цитата: «Q4 retry ownership and Q5 bounded resources also apply» —
только отсылка); `lifecycle.md` «Directories and files» (append-журнал `audit/<sub>controller/e1/…`, объекты
pass report и shard — без бюджетов); «Implementation decides» (11 пунктов — память/диск/fd не названы).

**Почему находка.** Ростущее состояние процесса нормативно не ограничено и не измерено ни в одном носителе:
память наблюдений (heartbeats/slots/resources читаются каждый pass, объём растёт с размером кластера),
буферы сериализации snapshot-шардов (до потолков L/SNAPSHOT_TABLE_MAX), append-журналы audit/audit.alarms,
число отслеживаемых intent/pending. Память сервера по ролям — «the common memory ceiling of a server over all
roles is a limit of the scheme (R12)» (N3 shortage) и memory check скрипта воркеров (P/02.4 N1.5, P/03.4
budget) — владельцы P/02.4/P/03.4, а не P/04; для самого процесса контроллера ни бюджета, ни единицы объёма, ни
пробы saturation нет. Контрпример-асимметрия: для объектов и батчей decommission единицы и потолки названы
(п.6 матрицы), для собственных ресурсов процесса — нет ни одной.

**Disposition.** production-obligations: «finite memory, disk, descriptor, queue and admission budgets and the
workload units to which they apply» — конечный бюджет объявляет реализация; новых чисел не вводится. Проба среды
в реестре отсутствует. Рекомендация: в «Implementation decides» добавить пункт с именованными единицами роста
(наблюдения на pass, байты журнала, буферы сериализации) и привязать к п.10 чек-листа.

### Н3 (М, proposal, п.6) — Устаревшее слово-регулятор в N1.3a: «raising OBJECTS» вместо max_bytes

**Место.** `spec/04-controller.norms.md` N1.3a `ceiling`, последняя строка диагностики: «raising OBJECTS does
not lift the door limit».

**Контрпример.** В реестре `OBJECTS` — адресная переменная окружения (`forms/daemon-flags.tsv`:
`$OBJECTS string - file://; cluster:// with configstore`), её «поднятие» бессмысленно; регулятор размера
объекта хранилища называется max_bytes: `acceptance/README.md` «Snapshot outside TSV» — «max_bytes=0 does not
remove the ceiling of the door»; `forms/refusals.tsv` строка 17 — «raising max_bytes helps only up to the
resource door limit L». Смысл совпадает, слово — нет; читатель формы не сможет действовать по фразе.

**Рекомендация.** Заменить «raising OBJECTS» на «raising max_bytes» (слово владельца потолка хранилища) и
снять расхождение с refusals.tsv.

### Н4 (М, норма есть — пробы нет, п.6) — `seconds` отчёта не имеет исполняемой пробы

**Место.** N1.2: «`seconds`: <duration of the control part, excluding later snapshot/report publication>»;
семейство `controller-pass` (`seconds: number; ≥ 0`) — в сценариях не сравнивается.

**Почему находка.** Семантика поля (control part кончился до публикаций) нигде не проверяется исполнением:
seams s57–s63 фиксируют порядок turn release → snapshots → один final report (`turn_released_before_snapshots`,
`publications_before_report`, `pass_report_writes`), но не `seconds`; TSV сравнивает `snapshot_*`-счётчики и
`at` (@time), `seconds`/`last_success` не сравниваются. Норма остаётся только чтением.

**Рекомендация.** Либо добавить в s57–s63 наблюдение `seconds` (control part < полного цикла с публикациями),
либо явно записать в N5, что поле проверяется чтением.

### Н5 (М, норма есть — пробы нет, п.11) — RAISE_QUIET и эскалация RAISE_FAILS_LOUD без исполняемой пробы

**Место.** `forms/runtime-constants.tsv`: RAISE_QUIET=600 s («quiet interval for a server that failed to raise»),
RAISE_FAILS_LOUD=3; N1.4 + N3 «withdraw on deadline» («the server «failed to raise» for RAISE_QUIET … after
RAISE_FAILS_LOUD in a row — of raised severity»); `refusals.tsv` строка 12.

**Почему находка.** Потолок сценария 3 минуты (`acceptance/README.md`: «One scenario takes no longer than 3
minutes»), RAISE_QUIET=600 s в него не помещается; sc.15 наблюдает `raise_failed` однократно после WANT_GRACE
(90 s) и перевод заказа на другой сервер, но не 600-секундную тишину и не эскалацию после 3 подряд. Виртуальные
часы seams покрывают только WANT_GRACE re-path (s32); кейса с монотонной шкалой для RAISE_QUIET/RAISE_FAILS_LOUD
в реестре нет.

**Рекомендация.** Добавить в `controller-want` (или controller-pass) кейс на виртуальных временах: N подряд
неподъёмов → нет заказов RAISE_QUIET, `raise_failed.times` растёт, после RAISE_FAILS_LOUD — alarm повышенной
серьёзности, снятие при подъёме.

### Н6 (М, норма есть — пробы нет, п.3) — TURN_BUSY_RETRY как задержка повтора без исполняемой пробы

**Место.** `forms/runtime-constants.tsv`: «TURN_BUSY_RETRY 5 s — retry delay after busy admission; independent
current source sentence, not TURN_RENEW by equal value»; N3 step 0: «busy → no changing pass, a retry after
TURN_BUSY_RETRY»; `refusals.tsv` строка 6 (turn busy → «a retry on the next pass»).

**Почему находка.** Значение и норма есть, исполняемого наблюдения задержки повтора (5 s) нет: busy-ветка
turn-векторов — общая (common/vectors/turn, владелец common), в P/04 гонки двух контроллеров — «checked by
reading» (N5), сценариев с живым чужим holder'ом моложе TURN_TERM нет (sc.32 пишет чужую строку turn по
`manifest_rev`, но контроллер лишь не берёт turn, повторной задержки не наблюдается). Расхождение формулировок
«retry after TURN_BUSY_RETRY» (norms) и «retry on the next pass» (refusals) при PASS_EVERY=5 с не приводит к
противоречию значений, но семантику задержки не закрывает ничем.

**Рекомендация.** Либо добавить наблюдение задержки повтора после busy (stand с двумя контроллерами или
scripted holder), либо записать в N5, что задержка проверяется чтением/владельцем turn-векторов.

## Сводка

- Полнота применимости: 14/14 оценены; ✅ 9 (п.2, 3, 4, 6, 8, 11, 12, 13, 14), ✅/➖/⚠ смешанные 2 (п.5, 9),
  ⚠ missing-input 1 (п.10), ➖ 2 (п.1, 7).
- Находки: **Б0 / С2 / М4** (Н1, Н2 — существенные missing-input с disposition «конечный бюджет объявляет
  реализация»; Н3 — proposal по формулировке; Н4, Н5, Н6 — норма есть, исполняемой пробы нет).
- Противоречий (норма против нормы с контрпримером) не зафиксировано; семантика WRITE_CONFLICT_LIMIT
  (norms/runtime-constants/refusals/seams s54–s55) и границ SLOT_TERM/LOST_AFTER/HUNG_MOVE_AFTER
  (norms/slot-fate/sc.26–27/seams s1–s16) согласованы.
- Ничего в Source не правилось; отчёт — единственный добавленный файл. Блокеров нет: работа выполнена на
  назначенном пине, ростер сверен, все 14 пунктов получили статус с якорем/пробой/причиной.

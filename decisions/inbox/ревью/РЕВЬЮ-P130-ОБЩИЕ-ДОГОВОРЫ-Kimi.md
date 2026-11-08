# РЕВЬЮ боевых свойств — единица «общие договоры Platform/common/contracts» — Kimi (review103-kimi)

2026-11-08. Рецензент: review103-kimi (CT 103). Единица нормативного ревью по ADR-0130 Addendum (4), (5).
Независимый отчёт: чужие отчёты, outcome-summary, черновики и модель Quint до обеих сдач не читались.

## Основание и вход

- Задание: `/home/pilot/coord103-src/adr0083-144-tools-handoff-20261108/adr0130-production-review-units-f8ce/COMMON-CONTRACTS-UNIT-TASK.json`,
  SHA-256 `ec1fc0bbc5cfaa17d70fda80aafedac194169c3a6336b199f2c14cf214968273` (совпал при чтении).
- Source pin: `f8ce0f5246e4a9f078702b3acd6bc4effbb3a1f5` (своя ветка `kimi103/review-p130-common-contracts-f8ce`, worktree `/home/pilot/wt-kimi-p130-common`).
- Полномочие: ADR-0130 доп. (4) (12→14 пунктов по доп. (5)), доп. (5) п. 4: общие договоры `Platform/common/contracts/` —
  отдельной единицей, в уроках только ссылка.
- Метод: `skills/platform-review/SKILL.md@f8ce0f52` и `references/signals.md` прочитаны, адаптировано к нормативному
  Source (TEXT-only; без SUT/Go/HTTP/прогонов; Quint не строил — одна модель у review103, читается отдельной поздней фазой).
- Бюджеты: новые числа не вводились; выбранный disposition доп. (5) п. 3 — «конечный бюджет, объявленный реализацией» +
  проба с входом от среды; фиктивных значений и PASS нет.

## Охват

- Первичный состав: все **44 файла** `Platform/common/contracts/` прочитаны **целиком** на точном пине (не diff-only).
  Сверка blob-хешей: 44/44 совпали с `primary_roster` задания (проверка `git ls-tree f8ce0f52` против JSON-задания,
  расхождений нет).
- Необходимые прямые Platform-ссылки вне ростера (почему прочитаны, фактические места):
  1. `Platform/01-store/spec/01.1-store.norms.md` N0 «Cluster clocks» (строка 78) и P/01.1-27 (строка 904) —
     допуск расхождения часов `CLOCK_SKEW` (для п. 13); чтение формы `forms/runtime-constants.tsv` по ссылке.
  2. `Platform/01-store/spec/01.1-store.norms.md` N2.1 «Early refusal» (строки 353–354, R050) — общее правило
     «ответ с `Connection: close`, затем ограниченный слив», объём/срок объявляет реализация (для п. 2, часть drain).
  3. `Platform/03-worker/spec/03.6-worker.norms.md` N1.5 (строка 126) — `PERFORM_TIMEOUT: 10`, `PERFORM_GRACE: 0.2`,
     `REQUESTS_HOLD: 0.5`, `COMMANDS_PER_LOOK: 200` (для п. 3/9, сторона holder'а).
  4. `Platform/06-console/spec/06.4-console.norms.md` N1.5 (строка 110) — `CLEAR_EVERY`, `SWEEP_EVERY`, `REAP_AFTER`
     в форме констант (для п. 9/14, reaper).
  5. `Platform/common/data/codec.tsv` (строки 1–12) — кодек `time` (писатель ≤3 дробных цифры, читатель tolerant;
     для п. 13, времена в строках/метках).
- Границы: нормы уроков-владельцев (P/01–P/10) не перечитывались целиком — только названные точечные ссылки;
  приёмка/лекции не источник; VMS и замороженный Source вне объёма (ADR-0083 доп. (146)); отсутствие этапа-3
  как само по себе не находка (по заданию).

## Матрица 14 пунктов × составных частей

Статусы: `н+п` — норма и проба названы; `п-` — норма есть, пробы нет (finding о пробе); `бюджет` — норма/бюджет
отсутствуют (finding «нет бюджета», закрытие выбранным disposition); `н/п` — неприменимо с причиной. «Проба» —
векторный пакет common или сценарий приёмки владельца, названный контрактом.

| Пункт (части) | Статус | Нормы/пробы (файл, место) |
|---|---|---|
| 1. connection limit | бюджет | Общий предел соединений на дверь в common не нормирован; механизмы частичных пределов есть: lanes (gate-and-pass.md, порядок шагов 1: reserve/monitor/feed/callback/streams/common, busy → 503 busy; числа у владельца P/06.5 N4), `PASS_STREAMS_MAX: 256` (gate-and-pass.md, pass второго вида), KNOCKS ≤64 (accept.md). Finding М2а (бюджет; disposition — конечный бюджет реализации + проба среды, новых чисел нет). |
| 1. request limit | н+п | REPORT_RATE для class camera в секунду (accept.md «Busy»; память процесса domain, забвение при restart названо пределом); лимиты попыток входа (gate-and-pass.md «Attempt limit»: per_address 5/900 s, ceiling 20/900 s → 1 попытка/60 s; verify: `VERIFY_FAIL_MAX: 20`, `VERIFY_NAME_FAIL_MAX: 10` с атомарными резервами); `GLASS_SESSIONS_MAX: 256`; `per_person` (request-mark.md, манифест); `COMMANDS_PER_LOOK: 200` (P/03.6 N1.5, ссылка). Пробы: сценарии приёмок 6.3/6.7/P10/8.4 (по тексту контракта). |
| 2. read timeout | н+п | local-token-door.md «framing»: «the input of the whole request ≤ 10 s, otherwise 400»; gate-and-pass.md: `BODY_WAIT: 5` (slow body → 408, default, override — deployment); store-client.md: «answer read limit and wait term — decided by the client implementation, which names them» (конечный бюджет реализации); merge: 3 s на ответ ресурса (events-merge.md шаг 1); `PASS_WAIT: 5`, `FORWARD_WAIT` по таблице дверей (5–100 s). Пробы: acceptance-сценарии, векторов у части нет — по тексту «checked by the scenarios/reading». |
| 2. idle timeout | бюджет | Простой keep-alive соединения общих дверей в common не нормирован (у локальной двери «one exchange per connection, Connection: close» — keep-alive нет вовсе). Finding М2б (бюджет; disposition тот же). |
| 2. drain (объём/время, порядок «ответ, потом слив») | н+п | Порядок и ограничение слива нормированы ссылкой на P/01.1 R050 (gate-and-pass.md «Early refusal»: полный отказ с `Connection: close` первым, затем сырой слив, ограниченный длиной/лимитом байтов/абсолютным монотонным дедлайном; trickle не продлевает; без второго отказа); объём и срок объявляет реализация (P/01.1 N2.1 строка 354). accept.md: 413 при `BODY_LIMIT` — «the body is not read further» (дочитывания нет; отдельный слив не нормирован). forwarding.md: «the body is never cut». Граница владения: «console slow-body 408/BODY_WAIT — здесь; forwarding/pass/stream budgets — у владельцев» (gate-and-pass.md Early refusal). |
| 3. lock waiting deadline | н+п + бюджет | Нормированы: `TOKEN_WAIT: 10` → 503 unavailable (local-token-door.md); `TURN_TERM: 45` — захват чужого turn после неизменности ≥45 s (turn.md, шаг 2); `START_WAIT = 60` — ожидание чтения `platform/schema` при старте, иначе code 1 (schema.md). Не нормировано: срок блокирующего `flock` при старте worker'а (presence-lock.md — «exclusive blocking flock… without LOCK_NB»); честно оговорено: «the answer term of an unavailable store is not bounded by this» (turn.md, Races). Finding С2. Пробы: векторы `turn`, acceptance P/03.2/P/04/P/08.10/P/09.1. |
| 4. barrier | н+п | turn.md «Barrier»: любой неизвестный исход/конфликт/412 прерывает план; продолжение только после подтверждённой смены версии turn; неизвестный исход самого барьера запрещает продолжать; «старая запись либо видна до барьера, либо 412 после». Векторы `turn` (33+16 случаев). |
| 4. write failure | н+п | event-journal.md: «an alarm and the journal — fsync of the line and of the directories up to the root; an observation — no»; I/O-ошибка — ошибка вызывающему, без автоматического повтора. object-client.md `put_durable` — барьер долговечности до публикации (ссылка P/06.1 N1.5). Векторы `journal` (append.tsv). |
| 4. ambiguous и повторная видимость | н+п | store-client.md: `ambiguous` → повтор только с тем же `id`; `again: true` — ответ сохранённого повтора; no_reply для записи = ambiguous. request-mark.md: один исход (первый подтверждённый), `late: true` позднего ответа, conflict → reread и повтор только записи. Векторы `store-client`. |
| 5. exclusive data directory | н/п в common (норма у владельца P/01.1/ADR-0130 доп. (2) — вне ростера; здесь не пересчитывается по заданию) | В common смежное: directory lock `<dir>/~lock` flock(LOCK_EX) на время записи объекта (event-journal.md «File names»); «one writer per bucket» под flock LOCK_EX (event-journal.md writer). |
| 5. exclusive address | н+п | local-token-door.md «The role socket»: stale socket (ECONNREFUSED → удалить и создать), «connect succeeded or another error — busy, a start refusal», `bind → EADDRINUSE — a start refusal`; только Unix-socket на боксе; TCP-вариант — open question (не нормирован, открытый вопрос P/09.1 N5). Пробы: acceptance P/09.1/P/03.7, чтение (LTD-STALE-PATH-33-01: «by reading»). |
| 5. leadership / resource ownership | н+п | turn.md: CAS-захват turn, `TURN_TERM/TURN_RENEW`, guard, сдача в конце pass и на SIGTERM (operations/signer), «the old holder does not renew and does not release a foreign turn»; operations-turn (P/06.9 N3, ссылка). Векторы `turn`; гонки двух claimants — acceptance P/04/P/08.10/P/09.1/P/06.9 + чтение. |
| 6. write cost with volume | бюджет | Стоимость операций общих функций в common не нормирована; ед.объёма и зависимость названы ниже (§ «Рост»). Содержательное место: gate-and-pass.md — trust gate читается на каждый запрос без кэша (порядок шагов 3), мемоизация только ролей («once per version of the copy, not per check») — стоимость проверки права растёт с размером копии grants/roles; бюджет отсутствует. Finding М2в (бюджет; disposition тот же). |
| 6. import cost with volume | н/п в common (импорт — ядро P/01.1, вне ростера; общие договоры импорт не выполняют) | — |
| 6. unit of volume and growing states | н+п (как обязанность отчёта) | См. § «Рост» ниже. |
| 7. message/body framing | н+п | local-token-door.md: TE вместе с CL → 400; ambiguous/incomplete → 400; строка запроса и заголовки ≤16 KiB; gate-and-pass.md: chunked → 400; повтор читаемого параметра → 400; ранний отказ до исполнения (порядок шагов). Пробы: acceptance-сценарии участников, чтение (у local door «no vectors» по тексту). |
| 8. backup/export | н+п (частично: копирование/выгрузка) | object-client.md: `scope=cluster` — свежая копия по `written` wins; `X-Missing` — неответивший сервер, не отсутствие; 404 «absent among those that answered»; tombstone.md: копия старше `written` tombstone удаляется соседом, 409 «deleted later»; alarm-history.md `in_copy` — история едет с backup-копией holder'а. Пробы: векторы `object-client` (address/read), `tombstone`. Сама операция backup (D6/P/01, P/08.8 N1.5) — вне ростера. |
| 8. incomplete result | н+п | events-merge.md: `incomplete{<server>: did not answer|silent|said <state>}`, `complete = incomplete пуст` («completeness of the sources that answered…, not the absence of a cut by limit»); `truncated` и `partial` — честные счётчики этапов («not the number of different lost events»), «there is no additional reading of hidden rows»; поздний ответ — в `incomplete` этого ответа, не добавляется к выданному. Векторы `events-merge`. |
| 9. restart | н+п | observation.md: память наблюдателя «begins anew after a restart» (ADR-0049), первое наблюдение fresh (age 0); request-mark.md: возраст строки после restart «begins it anew: an unknown age does not count as expired»; accept.md: `busy`/knock-память процесса забывается при restart — «the silence term is one round shorter, that is the limit»; gate-and-pass.md: записи тикетов только в памяти (restart → нет записей). Пробы: fresh-age/resource-state, acceptance 6.4/3.6. |
| 9. graceful stop deadline | бюджет | Сдача turn нормирована (turn.md: конец pass, SIGTERM у operations/signer); watchdog 360 s SHOULD (env-file.md «Constants», P/02.4 N1.1/P/03.3 N1.2); срок штатной остановки процесса с завершением принятой работы в common не нормирован (D4-подобная норма — у P/01, вне ростера). Finding М2г (disposition тот же; частично покрыто P/03.6 PERFORM_TIMEOUT для стороны holder'а). |
| 9. cancellation | н+п | forwarding.md (pass policy): «Ordinary cancellation… close downstream work; they… do not release application write guards early»; монотонный дедлайн hop'а «without resetting it on a header, chunk or retry»; gate-and-pass.md: тикет удаляется по окончании внешнего запроса; открытые стримы проверяются «at least once per `PASS_TICKET_CHECK`» (5 s) на revocation/disabling/exp и закрываются; stream после заголовков клиента — только байты и закрытие. Пробы: seams/sценарии 6.7/P10 (forwarding). |
| 9. fate of admitted work | н+п | gate-and-pass.md: «a call that has passed `ticket` runs to its end: one write is atomic, and the next call gets 401»; store-client.md: исход `ambiguous` — решение о новой записи у вызывающей нормы; turn.md: неизвестный исход своей записи turn — перечитать и подтвердить, не считать успехом (C08-TURN-SELF-99). Пробы: векторы `turn`, `store-client`. |
| 9. resource release | н+п | local-token-door.md: при выходе агент удаляет только свой путь и только при совпадении dev/ino (LTD-E03); presence-lock.md: lock держится всю жизнь процесса, освобождается выходом (включая смерть процесса — flock ОС); gate-and-pass.md: закрытие тикета/стрима, освобождение lane; accept.md: «keep: the two last generations… older ones removed by the next acceptance» — граница хранения поколений. Пробы: acceptance/чтение. |
| 9. recovery | н+п | schema.md: ошибка чтения `platform/schema` → ждать без работы до `START_WAIT = 60`, иначе code 1 (supervisor restart); damaged/too new → code 2 без restart; object-client.md: неответ/нечитаемость door row → «unknown, not absent», перечитывается при следующем доступе; event-journal.md: `written` бакета сохраняется через restart/reindex; role-certificate.md: `revoked`/crl перечитываются по содержимому без restart, новые соединения видят изменение. Пробы: векторы `schema`, `object-client`, acceptance P/05 (sc. 17/18). |
| 10. memory limit | н+п | accept.md: KNOCKS ≤64 (память процесса, evict старейшего), keep 2 generations, `rev ≤ 2^53−1` (rev_exhausted → 503); gate-and-pass.md: `GLASS_SESSIONS_MAX: 256`, `PASS_STREAMS_MAX: 256`; alarm-history.md: `HISTORY_LINES: 2000`, `HISTORY_DAYS: 7`; presence-lock.md: `room = min(floor(HOST_MEMORY_MB/WORKER_MEMORY_MB) − live, 98 − live)`; env-file.md: `CAPACITY/WORKER_MEMORY_MB/HOST_MEMORY_MB` (ADR-0070); request-mark.md: `FETCHED_COUNT/FETCHED_BYTES` — «named by the implementation in its description» (конечный бюджет реализации). Пробы: векторы accept/presence-room/fresh-age. |
| 10. disk limit | н+п | Пределы объёма: объект >64 MiB → 413 (object-client.md); `BODY_LIMIT: 16 MiB` (accept.md); `BATCH_LIMIT = 4 × BODY_LIMIT` (accept.md, значение из формы P/08); `FORWARD_MAX: 1 MiB`, pass-buffer 4 MiB (forwarding.md, gate-and-pass.md); json-поле >4000 байт канонического текста → 400 (row-check.md); имена компонентов >255 байт → `%h`-sha256 + `.name` (event-journal.md). Пробы: векторы object-client/row-check/journal names. Общий дисковый бюджет (место) — не нормирован, см. М2д. |
| 10. descriptor limit | бюджет | Пределы дескрипторов в common не нормированы. Finding М2д (бюджет; disposition тот же). |
| 10. unit of volume and growing states | н+п | См. § «Рост». |
| 11. queue backpressure | н+п (частично) | local-token-door.md `no_queue`: очереди ответов нет; запрос держится не дольше `TOKEN_WAIT` → 503, «the worker asks again»; gate-and-pass.md: lanes (отдельная полоса для streams, `PASS_STREAMS_MAX`); accept.md: публикация relay в памяти, повтор после `retry_in`, новая приходящая заменяет (граница `BATCH_LIMIT`/`KNOCKS`); events-merge.md: `limit` (1000, ceiling 10000) обрезает выдачу, `truncated` — счётчик, не блокировка. Пробы: векторы events-merge/accept. Общая очередь запросов holder'а — сторона владельца (P/03.6). |
| 12. dependency unavailability | н+п | Исходы нормированы: store-client.md 503 `unavailable` → «repeat at the next step» (с `Retry-After` — не раньше срока), `ambiguous` → same id; gate-and-pass.md «Unreadable row» → 503, не 401/403, не «нет строки»; schema.md: ждать `START_WAIT`; local-token-door.md: holder/relay молчат → 503, worker повторяет; peer.md: fail-closed (`foreign_ca`), лечение — rotation центра; role-certificate.md: `revoked`/crl испорчены → закрытый отказ для новых соединений, «less trust is safe»; events-merge.md: `incomplete`; pool.md: `requires: resource` — мягкая зависимость, «unknown is not a fact, the worker passes». Пробы: векторы store-client/peer/resource-state. Circuit breaker не вводится (повтор по сроку — норма). |
| 13. clock jump | н+п | record.md: `at` строго растёт, «a clock going back — the former + 0.001»; tombstone.md: `written = max(now, removed_written + 0.001)` — «strictly greater… even when the wall clock is equal or has moved backwards»; accept.md: `sent_at` назад на той же дороге «taken at once»; observation.md: «the clock of the writer does not prove freshness» — скачок писателя не омолаживает версию; W2C_WALL_OFFSET (env-file.md, stand hook). Пробы: векторы alarm-history (t/t_src), tombstone, record. |
| 13. clock skew | н+п | domain-token.md: `TOKEN_SKEW: 60` в обе стороны, границы `exp+60` ok / `iat−60` → `future` («check the clock»); векторы domain-token (границы). agent-signature.md: `MEMBER_WINDOW: 300`, `UNIT_WINDOW: 60`, в обе стороны; векторы agent-sig. ask-sig.md: `skew` при >300 s; векторы ask-sig. may.md: `GRANT_LIFETIME: 86400` (stale-копия). peer.md: `MEMBER_ROW_AGE: 3600`. Допуск кластера: P/01.1 N0 «Cluster clocks» — ≤ `CLOCK_SKEW` (посылка развёртывания, P/01.1-27 — проверяется чтением). |
| 14. retry behavior | н+п | Идемпотентность: store-client.md — повтор только с тем же `id`, `again`; accept.md — повтор по `(sent_at, request_sha256)` → same/heard, шаг 2a (road_quiet) против гонки дорог; request-mark.md — повторы подачи по `digest` (queued/answered), `kept` ≥ `max(60, ttl)` — гарантия повтора переживает строку; gate-and-pass.md — `Retry-After` по ключу, который сработал (verify: pair/name/author). Пробы: векторы accept/store-client/request-digest. |
| 14. retry storm | н+п | Ограничители частоты: attempt-limit окна 900 s с `Retry-After` (gate-and-pass.md); accept.md `busy` 429 с `retry_in` — «the agent does not call the doors earlier»; store-client.md/object-client.md — «repeat at the next step», с `Retry-After` не раньше срока; tombstone.md — опрос соседа/ack раз в 10 мин; events-merge.md — поздний ответ не добавляется; event-journal.md — «an I/O error — without an automatic repeat». Резервная защита от шторма — сами пределы частоты; отдельного rate-limiter на все повторы в common нет (не требуется нормами). Пробы: acceptance-сценарии. |

## Рост (пп. 6, 10): единицы объёма и растящие состояния общих договоров

- **События журнала** (event-journal/events-merge): строки событий по деревьям `<sub>/<unit>/e<epoch>`; растёт с числом units и частотой событий;
  пределы: span бакета 600 s, `JSON_DEPTH: 128`, limit/ceiling выдачи 1000/10000; чтение — torn/garbled/duplicate счётчики, не отказ бакета.
- **Отчёты членов** (accept): `objects` публикации; растёт с числом объектов каталога; `BODY_LIMIT: 16 MiB` на тело, `whole_too_large` на JCS
  целого; хранение — два последних поколения, старшие удаляются следующей приёмкой; число поколений ≤ 2^53−1.
- **Метки/запросы** (request-mark): ряды `<sub>/requests/<rid>` и метки `commands/<rid>`; растёт с числом запросов; `per_person`, `ttl`,
  `settle`, `kept`; метки append-запросов накапливаются одна на rid (очистка не вводится — осознанное решение контракта).
- **История тревог** (alarm-history): строки истории члена; `HISTORY_LINES: 2000`, `HISTORY_DAYS: 7`, `cut_before` не убывает.
- **Сессии/стримы/стуки** (gate-and-pass/accept): открытые break-glass сессии ≤256, stream-пасы ≤256, стуки ≤64; растут с числом клиентов;
  память процесса, забывается при restart.
- **Правовые копии** (gate-and-pass/may): grants/roles копии домена; растёт с числом строк и ролей; trust gate читается на каждый запрос
  (стоимость растёт, бюджета нет — finding М2в); мемоизация ролей «once per version».
- **Присутствие/комнаты** (presence-lock/pool): lock-файлы `.workers/<sub>/<instance>`; `room` от `HOST_MEMORY_MB/WORKER_MEMORY_MB`
  и числа live-процессов (≤98 нумерованных).
- **Объекты** (object-client/tombstone): объекты и tombstone `.gone/`; 64 MiB на объект, копии по кольцу, ack-состояние tombstone
  (peers/acked) живёт ≥7 дней.

## Находки

### С1 — проба отсутствует: шаг 4a «whole_too_large» функции accept не имеет строки вектора

Тип: норма есть, пробы нет (probe finding). Место: `accept.md`, раздел «Vectors»: «There is no row for step 4a (`whole_too_large`) —
a candidate of the package (the README of the package, «Candidates»)». Норма (раздел «The function «accept»», шаг 4a:
«JCS(whole') larger than BODY_LIMIT → 413 {error: "whole too large", detail}; write nothing») не проверяется ни одной строкой
пакета `accept` (66 строк покрывают иные шаги). Цитата и проба взяты из файла, не пересказаны. Последствие: реализация может
нарушить норму «не писать ничего при превышении» без единой красной проверки; проверка делом (повтор 46c) не заменяет
предметной пробы шага. Разрешение: добавить строку в пакет `accept` (владелец — P/08.3/common по правилам векторов).

### С2 — срок ожидания блокирующего flock при старте worker'а не нормирован (бесконечное ожидание возможно)

Тип: норма/бюджет отсутствует (norm finding; disposition — конечный бюджет, объявленный реализацией, + проба среды, новых
чисел не вводим). Место: `presence-lock.md`, раздел «Lock», строка `the worker`: «at start, before the capture of a name:
open(O_CREAT) → an exclusive blocking flock (it waits while the resource releases the lock of its check; without LOCK_NB)».
Контрпример: resource того же бокса завис (или приостановлен) между своими проверками, удерживая flock файла присутствия, —
старт worker'а не завершается никогда; watchdog (notify «from the loop, not from the substitution», env-file.md) ещё не начался,
supervisor не получает code. Последствие: отказ бокса при зависшем resource не ограничен по времени; воркеры всех подсистем
бокса стартуют бесконечно долго. Смежная честная оговорка есть у turn.md («answer term of an unavailable store is not bounded
by this»), у presence-lock её нет. Разрешение: норма вида «конечный срок ожидания flock при старте, объявленный реализацией»
+ проба среды (приостановленный resource); число не вводится этим отчётом.

### М1 — проба отсутствует: `keys_sealed` и содержимое `sealed` без векторов (кандидаты названы)

Тип: probe finding (мелкая по последствиям — криптографические конверты). Место: `domain-envelopes.md`, раздел «Vectors»:
«`keys_sealed` and the content of `sealed` have no vectors — candidates (README of the package)». Открытие конвертов
(`x25519-open.tsv`, `m1-open.tsv`) и раунды покрыты; состав содержимого — нет. Разрешение: строки пакета `domain-envelopes`.

### М2 — общие бюджеты пределов (соединения, простой keep-alive, стоимость прав, остановка, дескрипторы/место) в common не нормированы (пять адресов одного класса)

Тип: budget findings, закрытие — выбранным disposition (конечный бюджет реализации + проба среды; числа не вводятся).
Не дефекты поведения: частичные механизмы и честные исходы уже есть (см. матрицу пп. 1, 2, 6, 9, 10). Ссылки матрицы
«Finding Б1–Б5» в прежней редакции отчёта — это адреса М2а–М2д ниже (метаданная правка, смысл и охват не менялись).
- М2а (п. 1, connection limit): общий предел числа соединений на дверь в common отсутствует; есть lanes
  (gate-and-pass.md, шаг 1; числа у владельца P/06.5 N4 — owner scope, вне ростера), `PASS_STREAMS_MAX: 256`, KNOCKS ≤64.
- М2б (п. 2, idle timeout): простой keep-alive соединений общих дверей не нормирован; у локальной двери keep-alive нет
  («one exchange per connection, Connection: close», local-token-door.md). Политика keep-alive дверей — owner scope
  владельцев дверей (P/03.4/P/06.5), здесь не пересчитывается.
- М2в (п. 6, cost of rights check): стоимость проверки права на запрос (trust gate читается на каждый запрос без кэша,
  мемоизация только ролей) не имеет бюджета; растёт с размером копий grants/roles.
- М2г (п. 9, graceful stop deadline): срок штатной остановки процесса с завершением принятой работы в common не нормирован;
  D4-подобная норма — у P/01 (owner scope, вне ростера); частичное покрытие: сдача turn (turn.md), watchdog SHOULD
  (env-file.md), PERFORM_TIMEOUT/GRACE для стороны holder'а (P/03.6 N1.5, ссылка).
- М2д (п. 10, descriptor limit и disk место): пределы дескрипторов отсутствуют; пределы размеров сообщений/объектов есть,
  общий дисковый бюджет (кончилось место) — исход не нормирован в common (у объектного дверя FS-ошибка после admission —
  отказ записи, object-client.md `writer`).

## Сводка

- Охват: 44/44 контрактов полностью на пине f8ce0f52 (blob-хеши совпали); 5 точечных внешних ссылок с фактическими местами;
  skill/signals прочитаны; TEXT-only, без прогонов и моделей.
- Статусы матрицы: все 14 пунктов и каждая часть получили собственный статус; молчания нет; неприменимость дана с причиной
  (импорт/backup-операции/владение каталогом — у владельцев вне ростера, не пересчитаны по заданию).
- Новых чисел не введено; отсутствующие бюджеты оформлены находками с выбранным disposition.
- Счёт: **Б 0 / С 2 / М 2** (С1 — проба whole_too_large; С2 — дедлайн flock; М1 — векторы sealed; М2а–д — пять budget-адресов
  одного класса посчитаны одной находкой). Это авторский счёт единицы; общий разбор — у SRC/Архитектора после обоих отчётов.

Один файл; ветка `kimi103/review-p130-common-contracts-f8ce` от `f8ce0f5246e4a9f078702b3acd6bc4effbb3a1f5`, main не трогалась.

# РЕВЬЮ P/06 — боевые свойства по ADR-0130 (5), чек-лист 1–14 (Kimi, review103-kimi)

Дата: 2026-11-08. Рецензент: review103-kimi (фоновый агент, CT 103).
Основание: ADR-0083 (152) прямой Dispatcher; ADR-0130 доп. (4), (5), (6); ADR-0154 (внутренний фоновый агент).
Задание: `/home/pilot/cammeta-sessions/dispatcher-tasks/2026-11-08-adr0130-p06-direct/review103-kimi-P06-TASK.json`,
sha256 задания `54ded1f854e41cf872a70c01215e0bb20fa44a8603c556824e15635d61e565e7`.
Source pin: `862455715be8e155e0c80566d6f60d443a8b2650` (опубликованный main; `git ls-remote` на момент задания совпал).
Идентичность ростера: все 54 файла `Platform/06-console/**` из `primary_public_roster` сверены с пином по git-blob, sha256 и числу байт — расхождений 0.

Отчёт — только ревью норм/форм/проб-контрактов на пине. Без правок Source, без прогонов, без моделей, без сети (кроме git fetch/push самого отчёта). Не объявляет whole unit / READY / GATE. Peer-исходы (P01–P05) не читались; прежние отчёты и архивы не читались и не переигрывались.

## Охват и пределы

Прочитано полностью: `spec/06-console.README.md`; нормы 06.1–06.9 целиком; `forms/README.md`, `forms/daemon-flags.tsv`, `forms/runtime-constants.tsv`, `forms/stages.tsv`, `forms/numeric-loader.cases.tsv`, `forms/deletion-body-witnesses.json` (структура и ключевые поля); README приёмки 1, 2, 4, 5, 6, 7, 8, 9; `seams.tsv` всех девяти глав; `lifecycle.md` (публичный ссылочный якорь этой единицы).
Прочитано точечно (структурно/поиском по темам 14 пунктов): `forms/refusals.tsv` (286 строк, 279 проекций; проверены шапка, покрытие кодов 400/408/413/429/503, строки c61_031_*, c64_011_*, c65_009_*), `spec/06-console.api.openapi.yaml` (общие ответы, Retry-After, wait-границы, описания 503/429), `scenarios.tsv` (выборочно по сценариям, названным README; объём 141 сценарий/1529 шагов целиком не перечитывался построчно).
Точечные общие якоря этого снимка (по фактическим ссылкам носителей): `common/contracts/gate-and-pass.md` (BODY_WAIT 5, PASS_WAIT 5, PASS_WAIT_MAX 9000, GLASS_SESSION 900, GLASS_SESSIONS_MAX 256, Early refusal/R050, order), `forwarding.md` (FORWARD_MAX 1 MiB, FORWARD_WAIT 5, буфер 4 MiB на хоп), `observation.md` (LOST_AFTER 45, lapse), `events-merge.md` (8 линий, 3 s), `turn.md` (TURN_TERM 45, TURN_RENEW 10), `store-client.md` (BATCH_WRITES/BATCH_GUARDS), `01.1-store.norms.md` (BATCH_WRITES форма). Common-единица рецензируется отдельно; здесь эти ссылки — только якоря, их находки не пересчитывались.

Честный предел: построчную сверку всех 279 строк refusals.tsv, всех 141 сценариев TSV и 404 KiB OpenAPI не выполнял; вердикт по ним — структурный, с точечными выборками. Это не снижает выводы по матрице, но названо как предел.

Граница единицы: P/06 — процесс консоли (`console`, один на сервер; `lifecycle.md`), обслуживающий байты модуля P/07 (модуль без собственного процесса). Части п. 9 о владении процессом/юнитом делегированы P/02.4/P/02.3 (systemd, runner) — отмечено как «неприменимо с причиной / якорь на владельца». Формулировка задания «модуль консоли внутри процесса воркера» на этом пине не совпадает с нормами (консоль — отдельный процесс; воркер — адресат `door.pass`); ревью ведено по нормам пина.

## Статусы

- **АП** — якорь + проба (норма и проба/стенд-наблюдение есть в носителях единицы).
- **НП** — норма есть, пробы нет (probe finding).
- **МВ** — missing normative input: бюджет не объявлен, точка объявления названа; новые числа не вводятся.
- **Н/причина** — неприменимо с причиной.

## Матрица 14 пунктов × части

**1. Предел соединений и запросов.**
1a Линии запросов (приоритетная поверхность): НП — норма есть (06.5 N2: общая линия на маршрут, 503 `busy` + `Retry-After: 1`; reserve `/session` `/healthz`, monitor `/metrics`, feed `/changes`, callback, stream линии), пробы заполнения линии нет (06.5 N5: «TSV does not send parallel requests», C29 — by reading).
1b Числа линий: частично АП/МВ — feed 256 (CHANGES_SUBSCRIBERS_MAX), glass 256 (GLASS_SESSIONS_MAX), callback ≥ общей (06.5 «Implementation decides» п. 2), stream PASS_STREAMS_MAX; размеры остальных линий — МВ (точка: 06.5 impl-decides п. 2).
1c Входные лимиты запросов: АП — тела ≥ 1 MiB (06.1 N1.4, impl), blob 32 MiB и «at once — 2, beyond that 503 Retry-After» (06.1 N1.4), JSON-поле 4000 B, глубина 64, ключ 1024 B, BATCH_WRITES/GUARDS (01.1 N1), ключ идемпотентности 200 B, VERIFY_UNITS_MAX 256, сессия 16 KiB (06.5 impl-decides п. 2).
1d Предел числа TCP-соединений/fd: МВ — не объявлен; точка объявления: 06.5 impl-decides п. 2 («limits … the lanes and their sizes … timeouts»).

**2. Тайм-ауты чтения и простоя, слив тела.**
2a Чтение тела: НП(проба) — норма есть: BODY_WAIT 5 s по умолчанию, деплоймент переопределяет (gate-and-pass `body`); 408 в refusals.tsv (c65_009_408, c64_011_408) и OpenAPI (SlowBody); проба slow body на стенде P06 отсутствует (acceptance/1: «The TSV does not send a large body»).
2b Простой соединения между запросами: МВ — idle-таймаут не объявлен; точка: 06.5 impl-decides п. 2 («timeouts»).
2c Слив тела при раннем отказе: НП(проба) — норма есть (gate-and-pass «Early refusal», копия R050: полный отказ, `Connection: close`, сырой слив без разбора, абсолютный монотонный дедлайн, лимит сырых байтов, chunked-финал не ждётся); числа бюджета слива объявляет реализация (явная оговорка контракта); пробы нет.

**3. Срок ожидания замка.**
3a Распределённые захваты: АП — очередь операций: writer-turn TURN_TERM 45 s / TURN_RENEW 10 s, барьер, give-up на SIGTERM (turn.md; 06.9 N3 «leader»); takeover claim после CLAIM_TAKEOVER_AFTER 30 s (06.1 N3); исчерпание повторов CAS → 503 (06.6 N2.1, 06.1 N3; периоды — 06.1 impl-decides п. 5); FOLDERS_TRIES 5 (06.8 N3); OPS_CONTROL_RETRIES 5 (06.9 N3; 6 проходов суммарно); sweep: CAS-конфликт списка → код 2, ничего не удалено (06.1 N2).
3b Внутрипроцессные замки консоли: МВ — сроки не объявлены (внутренние интерфейсы — выбор реализации, 06-console.README); частичный якорь исчерпания — 503 в процедурах выше.

**4. Барьер, сбой записи, ambiguous.**
4a Барьер/атомарность: АП — store batch all-or-nothing (01.1 N1; 06.1 N2 «Batch door»); внутренние батчи консоли ограничены весом, не числом строк (ADR-0095 § 2; 06.8 N3; 06.9 N1.6 «N + 3»); инвариант ссылок папок — один батч (06.8 N1.1); done claim — записью того же батча (06.1 N3 «batch»); пробы: seams s05 (CAS-отказ списка до первого удаления), s06–s11 (продолжение claim), console-op-step-batch s03 (generation guard → 412, ничего не записано).
4b Сбой/неизвестный исход записи: АП — 5xx не становится done; pending сохраняется до подтверждения; отказ/неизвестный исход сохранения ответа → 503 (06.1 N3 «create» step 9); reaper: «unknown read does not allow row deletion» (06.4 N3, 06.8 N3); обрыв между записью и журналом признан (потеря строки журнала, 06.1 N3 «Races»).
4c ambiguous: АП — словарь исходов store; консоль: «unavailable, ambiguous, no answer → 503 store unavailable» (06.1 N3 «batch»); читающая операция консоли AmbiguousFault не создаёт (06.5 N2 по 06.1; ADR-0130 D6 — владелец дверей копии P/01, не дублируется).

**5. Исключительный захват ресурса: каталог данных, адрес, лидерство.**
5a Каталог данных: Н/причина — собственного каталога данных у консоли нет: корни создаёт роль до старта, процесс корни не создаёт (lifecycle.md «Stand», STAND-ROOTS-CLEAR-01); владение каталогом данных — store/P/01 (проба 5 З-21 ведёт spec103 по ADR-0130 доп. (2), Архитектор). Частичный якорь: ring обязан лежать вне известных корней (secret-files `forbidden`, lifecycle.md «Directories»).
5b Адрес: АП(частично) — listeners CONSOLE_HOST/CONSOLE_PORT/CALL_PORT, activation/kit/role checks по контракту сертификатов ролей (daemon-flags.tsv); callback listener открывается до readiness-порта (lifecycle.md «Signals and readiness»); один процесс консоли на сервер (06.5 N1.1). Проба «второй процесс на адресе» — у владельца активации listener'а (P/02.4/роль-контракт).
5c Лидерство: АП — один лидер операций на подсистему через очередь turn (06.9 N3 «leader», turn.md); консоль не участвует в лидерстве кластера (placement — P/04).
5d Модуль P/07: Н/причина — байты без процесса; публикация байт-в-байт (06.5 N1.1, sc. 01).

**6. Стоимость записи и импорта, рост с объёмом.**
6a Стоимость записи: АП(структурно) — create = 4 записи (claim, counter, row, done) с CAS/guard — O(1) на операцию, полные ключи не хэшируются (06.1 N3); edit/delete — 1 запись + claim; фид: один listing префикса за тик на всех подписчиков (06.1 N3 «feed», ADR-0094 B2); merge: 8 линий, 3 s (events-merge.md); удаление тел/папок — статический весовой конечный профиль с формулой `H + (n_unit+n_claim)*(12V+7) + n_folder*(6F+19) + 2*n_empty + LF ≤ B` (06.8 N1.3, ADR-0127 C2; свидетели deletion-body-witnesses.json).
6b Импорт: Н/причина — операции импорта у консоли нет; загрузка манифеста — P/02.1, установка — P/02.3.
6c Единицы объёма и растущие состояния: АП(перечень)/МВ(бюджеты) — единицы названы: строки (units/tables/requests/ops/folders), сообщения фида (≤ CHANGES_HISTORY 256), claims (терм ≥ DONE_ANSWER_KEEP 86400 s, способ очистки — 06.1 impl-decides п. 3), sweep-список ≤ 64, tombstones (не удаляются, кроме placement-условий), журнал (владелец P/05), accounting `asked` ≤ per_person. Верхняя граница объёма listing'а за тик фида при росте данных не объявлена — МВ (точка: 06.5 impl-decides п. 2/п. 4).

**7. Кадрирование.**
7a Запрос: АП(норма)/НП(проба) — HTTP RFC 9112; отклонения консоли: chunked → 400, повтор параметра → 400, короткое тело 400, превышение 413, медленное чтение 408 (06.5 N2/N4, gate-and-pass; refusals c65_009_*); Content-Length обязателен у bytes door (06.1 N2); framing/фактические байты проверяются до отправки в door.pass (06.5 N2 «door.pass»). Проба оборванного/chunked тела на стенде отсутствует.
7b Ответ: АП — HEAD без тела на всех GET (06.5 N2); буфер ответа door.pass до 4 MiB до заголовков, локальный 502 при превышении/обрыве (06.5 N2); forwarding: ответ как пришёл, FORWARD_MAX 1 MiB → 502 «answer too large» (forwarding.md; 06.7 N1.5); фид — обычный JSON long polling (06.1 N2); `/metrics` — текст экспозиции (06.5 N3); журнал — JSON Lines (06.4 N2); тело `{}` вместо пустого тела (06.6 N2.1).
7c Проприетарный протокол поверх HTTP: не выявлен ни в одном носителе единицы (копия — declared HTTP, 06.7 N1.13/N1.5).

**8. Backup и выгрузка, неполный результат.**
8a `/api/backup`, `/api/backup-part`: АП(консольная сторона) — ask-sig (401/403 по словам), непрочитавшаяся копия → 503 «not "none" — ask again», а не частичный ответ; нет части → 404 (06.7 N1.13); содержимое/сборка копии — владелец P/08.8 (не дублируется).
8b `/api/held`: АП — pointer {term, rev} или null; open door, невалидный Bearer — тоже 200 (06.7 N1.12; sc. 16).
8c Выгрузки/неполнота: АП — merge: `complete`/`incomplete` с именем потерянного источника, `truncated` — счётчик стадий (06.4 N2/N3, events-merge.md); `/manifest/<sub>/source` из памяти каталога старта, без чтения store (06.5 N2). Проба большого/оборванного ответа forwarding — by reading (06.7 N5: «there is no teaching door with a large or broken-off answer») — НП(проба).

**9. Перезапуск и штатная остановка (срок, отмена, судьба принятой работы, освобождение ресурсов, восстановление).**
9a Срок остановки: МВ — дедлайн SIGTERM→exit не объявлен (lifecycle.md «Signals» фиксирует семантику, не срок).
9b Отмена: АП(частично) — pause/resume/cancel операций (06.9 N2/N3, 409 на done), rebinding; DELETE /drain завершает drain; withdrawal decommission (06.6 N3); отмены принятой записи unit нет по конструкции (только обратная запись).
9c Судьба принятой работы: АП(диспозиция) — claims `<sub>/idem/*` остаются в store, повтор с тем же ключом завершает (lifecycle.md SIGTERM; 06.1 N3); requests остаются, reaper следующего процесса завершает (06.4 N3); лидер отдаёт очередь, новый держатель подхватывает (06.9 N3; seam-пробы console-op-* s01/s03/s04); ticket step call умирает вместе с вызовом; ticket door.pass — с запросом (06.3 N1.9).
9d Освобождение ресурсов: АП(частично) — give-up turn на SIGTERM и при отсутствии работы (06.9 N3 «leader» п. 5); sweepers останавливаются в окне (06.1 N3 «body sweep»); password_secret удаляется на ok/cancel (06.9 N3 «finish»); журнальный файлный замок — контракт журнала (P/05). Пределы (fd, сокеты) — см. МВ п. 1d/10c.
9e Восстановление: АП — reseal at start (нечитаемая строка → skip + log, старт не прерывается, 06.2 N3); repair `door/keys` следующим стартом (06.5 N3); reset фида и новый номер (06.1 N2 reset 1); recover `next_id` только по полному подтверждённому списку, иначе 503 и никакого автовосстановления (06.1 N1.3, seam s03); schema check at start: code 2, ошибка чтения — ожидание (06.6 N3); restart `Restart=always`, кроме кода 2 (lifecycle.md).

**10. Пределы памяти, диска и дескрипторов.**
10a RAM: АП(частично) — история фида ≤ 256 сообщений; glass-сессии ≤ 256; step ticket в RAM одного вызова (06.9 impl-decides п. 1); кэш байт статики допущен (06.5 N2). МВ — память тика фида (key→index по всем строкам области, 06.1 N3 «feed») и память наблюдений (06.5/06.6 lapse) растут с числом строк каталога, эвикция/бюджет не нормированы; точка объявления: 06.5 impl-decides п. 2.
10b Диск: АП(частично)/МВ — консоль пишет строки store (потолок 512 KiB на строку, 06.1 N1.4), tombstones, участвует в журнале/объектах (владельцы P/05); cleanup claims нормирован минимумом 86400 s, способ очистки — impl-decides (06.1 п. 3); числовой дисковый бюджет не объявлен — МВ (точка: impl-decides п. 3/п. 8 06.1, п. 2 06.5).
10c FD: МВ — пределы дескрипторов не объявлены; точка: 06.5 impl-decides п. 2.

**11. Обратное давление очередей.**
11a Линии: НП(проба) — 503 busy + Retry-After 1 при заполнении (06.5 N2/N4); feed-линия 256, ожидание ≤ CHANGES_WAIT 25 s (06.1 N2/N3); callback-линия собственная и ограниченная (ADR-0094 доп. (3) п. 7); stream-линия PASS_STREAMS_MAX (gate-and-pass); заполнение линий проверяется by reading (06.1 N5, 06.5 N5).
11b Лимиты предметной очереди: АП — requests per_person → 429, резервация не откатывается (06.4 N3; seams s01); операции: OPS_ACTIVE_MAX 64 / OPS_PER_PERSON_MAX 8 / OPS_PARALLEL 4 → 400/409, лимит судится чтением, допуск возможен «на одну сверх» (06.9 N3 —явная диспозиция); acceptance batch весом, не числом (06.9 N1.6).
11c Переполнение подписчика фида: АП — нет очереди на подписчика: отставание > истории = reset 2 (06.1 N2).

**12. Недоступность зависимостей.**
12a Store: АП — неподтверждённая обязательная запись/чтение → 503 `unavailable`/`store unavailable`, не успех по допущению и не пустой ответ (06.1 N2/N3, 06.5 N4, refusals c61_031_503 и др.); gate `shut` на потере trust → 503 denied (06.5 N4; seam console-gate s01).
12b Ring: АП — нечитаемый ring → 503 SealingUnavailable на любой POST/PUT до HMAC/claim (06.2 N1.2/N3; seam 2 s03).
12c Resource: АП — молчание источника → `incomplete`/lapse-память/`unknown`, не пустые строки и не доказательство отсутствия (06.4 N3 merge; 06.5 N2/N3; seams 5 s01/s02).
12d Доменные зависимости: АП — named codes: view.url нет → 503, CLUSTERS не читается → 503, member-list → 503, holder нет → 404, signer молчит → 502 (06.7 N1.4/N1.8/N3; seams 7 s01–s03).

**13. Часы: скачок и расхождение.**
13a Монотонные часы для возрастов: АП — возраст версий/свежесть/sweep-grace/delete_after/сleanup claims — монотонные часы наблюдателя, первый взгляд — fresh (observation.md; 06.1 N1.3/N3; 06.4 N3 tables; 06.5 N1.3); граница LOST_AFTER — вектор fresh-age.
13b Настенные часы и скачок: АП(диспозиция) — 06.9 N0: «OPS_KEEP and OPS_RUN_MAX are counted by the wall clocks … a clock shift shifts the deadline, but neither a step nor a right depends on it, because every step judges the token anew»; door token `expires = floor(now) + DOOR_TOKEN_TTL` (06.5 N3); valid_until записывается как прислано (06.4 N3 step 1).
13c Наблюдаемость расхождения: АП — `heartbeat_skew_seconds_max|min` (06.5 N3), `snapshot_ahead_shards` (ts > wall + 60 s, 06.5 N1.3), heartbeat из будущего → failover −1 / unmeasured (06.5 N3; sc. 21), `server_time` называет часы только этой консоли при CLOCK_SKEW (gate-and-pass `session`).
13d Проба границы: НП(частично) — вектор fresh-age есть, стенды P06 controlled clocks не имеют (06.5 N5, 06.6 N5: «the stand has no controlled clock»); частичные пробы skew есть (sc. 21, sc. 03/17).

**14. Повторы и шторм повторов.**
14a Серверные повторы ограничены: АП — повторы CAS с пределом (периоды impl-decides, исчерпание → 503, 06.1 N3; 06.6 N2.1); FOLDERS_TRIES 5 (06.8); OPS_CONTROL_RETRIES 5 (06.9); шаг: OPS_STEP_TRIES 3 с тем же step_key, серии retries/poisoned (06.9 N3; seams 9 s02); takeover claim 30 s отсекает двойное исполнение (06.1 N3 «Races»; seams 1 s06–s11).
14b Клиентские повторы: АП — идемпотентность по ключу на всех write-дверях людей (06.1 N3); «a request without a key is not repeated automatically» (06.1 N2); door.pass «Do not resend automatically» (06.5 N2); 429 с Retry-After на входных лимитах (login; break-glass: шестая неудача с адреса → 429, sc. 14; GLASS_SESSIONS_MAX 256).
14c Общий rate запросов: МВ — численный общий лимит входа не объявлен (имеются точечные 429); точка: 06.5 impl-decides п. 2 + N4.

## Findings

Одна причина — одна находка. Без новых чисел: где бюджета нет, находка называет отсутствующий вход и точку его объявления.

1. **(С, missing normative input) п. 1d/10c — предел числа соединений и fd процесса консоли не объявлен.**
   Место: 06.5 «Implementation decides» п. 2 называет «limits … the lanes and their sizes … timeouts» и даёт примеры (body, blob, session 16 KiB); линии нормированы структурно (06.5 N2), числа есть только для feed (256) и glass (256). TCP-соединения и дескрипторы под линиями HTTP не охвачены ни одним числом или именованным объявлением. Точка объявления: 06.5 impl-decides п. 2 (расширить список). Проба среды: насыщение соединений ниже уровня линий (accept-очередь, fd exhaustion) — поведение не определено нормой.

2. **(С, missing normative input) п. 10a — RAM-бюджеты растущих памятей консоли не объявлены: память тика фида и память наблюдений.**
   Место: 06.1 N3 «feed» — «The memory of the tick — key → index … revision, the tombstone mark, labels …» по всем строкам области всех манифестов; 06.5/06.6 lapse-память последних прочитанных версий. Объём обеих растёт с числом строк каталога; эвикция или конечный бюджет не нормированы (сравнение: история фида ограничена — CHANGES_HISTORY 256). Точка объявления: 06.5 impl-decides п. 2/п. 4. Проба среды: RSS при росте числа строк при неизменном CHANGES_TICK 1 s.

3. **(С, probe finding) п. 2c — слив тела при раннем отказе: норма есть, пробы нет.**
   Место: gate-and-pass «Early refusal» (копия R050, владелец правила — P/01.1): полный отказ → `Connection: close` → сырой слив «bounded by … the declared raw-byte limit and the absolute monotonic drain deadline … a trickle does not extend it and chunked discard does not wait for a terminal chunk»;явная оговорка «console … keep their own outcomes and declared limits», «console slow-body 408 and BODY_WAIT … remain owned here». В носителях P06 числа сливного бюджета нет (объявляет реализация — допустимо), но и пробы поведения (отказ до чтения тела + замедленная подача байтов) нет: acceptance/1 «the TSV does not send a large body», seams не покрывают слив. Probe finding, не missing-input.

4. **(М, missing normative input) п. 2b — idle-таймаут соединения между запросами не объявлен.**
   Место: объявлены BODY_WAIT 5 s (чтение тела после заголовков) и CHANGES_WAIT 25 s (long poll); таймаут простоя keep-alive соединения в носителях P06 отсутствует. Точка объявления: 06.5 impl-decides п. 2 («timeouts»).

5. **(М, missing normative input) п. 3b — срок ожидания внутрипроцессных замков консоли не объявлен.**
   Место: 06-console.README «The internal interfaces, types, error classes, functions, libraries … are chosen by the implementation»; распределённые аналоги числовы (TURN_TERM 45, TURN_RENEW 10, CLAIM_TAKEOVER_AFTER 30, FOLDERS_TRIES 5, OPS_CONTROL_RETRIES 5), исчерпание повторов CAS → 503 нормировано (06.1 impl-decides п. 5; 06.6 N2.1). Для собственных замков процесса (очередь тика, память наблюдений, claims в обработке) бюджет ожидания отсутствует. Точка объявления: 06.1 impl-decides п. 5 (периоды) / описание реализации.

6. **(М, missing normative input) п. 9a — дедлайн штатной остановки (SIGTERM → exit) не объявлен.**
   Место: lifecycle.md «Signals and readiness» фиксирует семантику (claims stay; requests stay; leader gives up the queue; restart Restart=always, кроме кода 2) без срока завершения и без правила для принятых HTTP-запросов в момент SIGTERM (диспозиция — восстановление через store повтором клиента, не drain ответов). Точка объявления: lifecycle.md «Signals» + описание реализации.

7. **(М, probe finding) п. 1a — заполнение линии (503 busy + Retry-After 1): норма есть, пробы нет.**
   Место: 06.5 N2/N4; 06.5 N5: «a lane is busy, 503 busy (C29): TSV does not send parallel requests» — by reading; 06.1 N5 (feed-линия CHANGES_SUBSCRIBERS_MAX + 1 → 503 busy) — by reading. Проба: параллельные запросы до отказа линии на обычном маршруте и на feed-линии.

8. **(М, probe finding) п. 7a — оборванное/неполное тело и chunked: норма и коды есть, пробы нет.**
   Место: 06.5 N4 + refusals c65_009_* (chunked/larger/slow/short → 400/413/408/400), OpenAPI SlowBody; sc. 16 шлёт превышение лимита целиком, а не обрыв. Проба: тело, оборванное посередине, и chunked-финал, которого нет.

9. **(М, probe finding) п. 13d — граница LOST_AFTER «включительно»: вектор есть, пробы на стенде P06 нет.**
   Место: свежесть — «age ≤ LOST_AFTER» (observation.md; изменение поведения № 1 у 06.5/06.6); вектор `fresh-age` назван, но 06.5 N5 / 06.6 N5: «the stand has no controlled clock» — by reading/vector. Частичные пробы skew есть (sc. 21 heartbeat из будущего, `snapshot_ahead_shards`). Проба: шаг ровно на 45 s контролируемыми часами.

10. **(М, probe finding) п. 8/7b — большой и оборванный ответ forwarding: норма есть, пробы нет.**
    Место: 06.7 N5: «a body of 1 MiB with 413 on the answering side, 1 MiB of an answer, «Wait» of a row, answer too large, answer broke off — the stand sends no bodies and answers larger than a MiB … there is no teaching door with a large or broken-off answer» — by reading. Проба: ответ члена кластера больше FORWARD_MAX и обрыв ответа по FORWARD_WAIT.

11. **(М, missing normative input) п. 6c/11 — верхняя граница объёма listing'а за тик фида не объявлена.**
    Место: 06.1 N3 «feed»: тик = list по каждому префиксу области при CHANGES_TICK 1 s; стоимость не растёт с числом подписчиков (норма), но растёт с числом строк; граница объёма listing'а/длительности тика (серия `w2c_changes_tick_seconds`) без бюджета. Точка объявления: 06.5 impl-decides п. 2 (лимиты) — без выдуманных чисел.

12. **(М, missing normative input) п. 10b — дисковый бюджет растущих строк консоли не объявлен.**
    Место: claims `<sub>/idem/*` (минимальный терм done 86400 s, способ очистки — 06.1 impl-decides п. 3), tombstones units (не удаляются, кроме placement-условий), строки audit (владелец P/05). Единицы объёма названы, конечный бюджет/политика удержания — нет. Точка объявления: 06.1 impl-decides п. 3/п. 8; 06.5 impl-decides п. 2.

13. **(М, proposal) runtime-constants.tsv, строка OPS_CONTROL_RETRIES — meaning нечитаем и допускает неверный вывод.**
    Цитата: «Conflict retries after original control pass, at most6passes». По 06.9 N3 «pause, resume, cancel» п. 5: «retry from step 1 at most OPS_CONTROL_RETRIES times after the original pass» — то есть 5 повторов + 1 исходный проход = 6 проходов; противоречия нет, но слитное «at most6passes» читается как «не более 6 повторов». Предложение: переформулировать meaning в «retries after the original control pass; original pass + retries ≤ 6 passes».

14. **(М, proposal) 06.5 «Implementation decides» п. 2 — назвать RAM, fd и соединения явно.**
    Сейчас пункт общим словом «limits» покрывает body/blob/session/lanes/timeouts; находки 1, 2, 4, 12 опираются на него как на точку объявления — явное перечисление «memory budgets (feed tick memory, observation memory), fd/connection limits, idle timeouts» сделало бы обязанность реализации проверяемой без новых чисел в норме.

15. **(М, proposal) lifecycle.md «Signals and readiness» — добавить строку диспозиции остановки.**
    Семантика SIGTERM есть, срока нет (находка 6). Предложение: строка «the stop deadline and the fate of admitted HTTP requests (drain vs close) are declared by the implementation» — тот же приём, что у 06.5 impl-decides, закрепляет владельца бюджета.

Противоречий (место + цитата + контрпример) на пине не выявлено: свежие вставки ADR-0127/0129 (finite deletion profile 06.8 N1.3; deletion-body-witnesses; source-until-restart 06.5; verify 503 форма; numeric-loader cases) согласованы с владельцами (вес вместо числа строк в 06.1 N2/06.9 N1.6; `exactly B is admitted` согласовано с witnesses V=1048576; CLAIM/OPS термы разведены в forms/README). New-meaning находок сверх уже принятых дополнений нет.

## Сводка

- Блокеры (Б): 0.
- Существенные (С): 3 (findings 1–3).
- Малые (М): 12 (findings 4–15).
- Итого: 15 находок: 0 contradiction, 5 probe findings, 7 missing normative input, 3 proposal.

Применимость: 14/14 пунктов применимы по частям (составные разложены); неприменимыми с причиной оказались только подчасти: импорт (6b, у консоли нет операции), собственный каталог данных (5a, владелец store/P/01, проба З-21 у spec103), процесс модуля P/07 (5d, байты без процесса).

Готовность к приёмке боевых свойств этим отчётом не заявляется: фактическая приёмка 17 групп — веха 2.4б на кандидате (ADR-0130 доп. (6), (8)); новые числа в нормы этим ревью не вносятся.

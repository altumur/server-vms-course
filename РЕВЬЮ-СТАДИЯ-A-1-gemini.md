# Ревью спецификации: стадия A (ADR-0083, доп. (2)–(4)), часть М10

- **Ревизия курса:** `5c0f19180` (`HEAD` ветки `gemini/review-stage-a-1`)
- **Предмет ревью:**
  1. `Platform/common/data/catalog.tsv` — строки М10 (`:1–58`, `:113`) против `М10_Platform/spec/*.norms.md`, `decisions/inbox/2026-10-18-каталог-данных-форма.md` и `decisions/inbox/2026-10-18-каталог-данных-вопросы.md`
  2. Абзацы «Данные» в `М10_Platform/spec/01..11-*.norms.md`
  3. `Platform/common/id-map.tsv` — 194 нормы М10 (`:1–200`) против `М10_Platform/spec/*.norms.md` и `Platform/module-design.md`
  4. Векторы: `Source/tests/testdata/*.tsv` (`canonical_json`, `fault`, `group_of`, `log_mask`, `platform_lists`, `requests_body`, `rid`, `secret_in`, `spec_verdicts`), `Platform/06-console/vectors/request-digest/*`, `Platform/01-store/vectors/rights-evaluator/*`, `Platform/common/vectors/README.md`
  5. `Platform/0[1-6]-*/lifecycle.md` против `М10/11` (и норм М10) и решений пилотов (`decisions/inbox/2026-10-18-пилот-хранилища.md`, `decisions/inbox/2026-10-18-пилот-кластера.md`)
  6. `НОРМАТИВНЫЕ-СЛОВА.md` и ссылки на него в `Н0`
- **Автоматическая проверка:** `python3 skills/lesson-spec/scripts/check_spec.py` → `Result: PASS with 22 exceptions`
- **Итоговый вывод:** **с правками**

---

## Отдельный вопрос: можно ли из `Platform/common/data/catalog.tsv` вывести тот же `configstore-rights.json`, что сейчас выводится из спеки (`М10/6 Н1.4`)?

**Ответ: нет.** Из текущего `Platform/common/data/catalog.tsv` нельзя механически вывести тот же `configstore-rights.json`, который порождается правилами `М10_Platform/spec/06-rights.norms.md` (`Н1.1`, `Н1.3`, `Н1.4`, `Н3`) и проверяется эталонами `Source/tests/testdata/acceptance/М10_Platform/06/variants/v1..v5`. Расхождения распадаются на четыре класса:

### 1. Широкие префиксы чтения и отрицания (`!`) в `М10/6 Н1.4` против построчного перечисления семей в `catalog.tsv`
- В `06-rights.norms.md:131–137` список `read` строится из широких префиксов с точечными отрицаниями `!<образец>`:
  - `console`: `<s>/*`, `platform/*`, `domain/*` (при наличии доменных ролей/ключей);
  - `<s>controller`: `<s>/*`, `!<s>/idem/*`, `!<s>/asked/*`, `platform/*`;
  - `<s>worker`: `<s>/*`, `!<s>/idem/*`, `!<s>/asked/*`;
  - `<s>domain`, `domain`, `domainagent`: `<s>/*`, `!<s>/idem/*`, `!<s>/asked/*`, `platform/*`, `domain/*` минус чужие секретные строки из `platform_lists.tsv` (`secret_readers`) и `secrets.readers`.
- В `catalog.tsv` столбец `readers` перечисляет читателей на отдельных семьях ключей. Прямая сборка `read` по строкам `catalog.tsv` даёт узкий перечень конкретных семей вместо `<s>/*` и `platform/*` и не порождает отрицаний `!<образец>`.
- При этом для `<sub>/asked/<sha16(имя)>` (`catalog.tsv:32`, `readers = console`) в тексте `06-rights.norms.md:132–137` выписано отрицание `!<s>/asked/*` у `<s>controller`, `<s>worker`, `<s>domain`, `domain`, `domainagent`, тогда как в `Source/tests/testdata/platform_lists.tsv` (`secret_readers`) и в эталоне `acceptance/М10_Platform/06/variants/v1-base/expect.tsv` отрицание `!cams/asked/*` отсутствует (есть только `!cams/idem/*` и `!door/signer`).

### 2. Правило `delete = write` по умолчанию (`М10/6 Н1.3`, `Н1.4`) против прикладных операций в `ops`
- По `06-rights.norms.md:80, 111` список `delete` роли в `configstore-rights.json` повторяет её `write`, кроме явных исключений «только `write` без `delete`» (`objects/<s>/commands/*` у `console`; `<s>/controller/placement_turn` и `<s>/controller/placement_intent` у `<s>controller`) и «только `delete` без `write`» (`delete: platform/doors/*` у `console`; `delete: <s>/<rows>/*` при `unplaced.delete_after` у `<s>controller` и при `worker.deletes` у `<s>worker`; `delete: <s>/<from>/*` по правилу R11 у `<s>worker`).
- В `catalog.tsv` столбец `ops` фиксирует только те операции, которые реально вызываются в шагах `Н3`. Поэтому в `catalog.tsv` нет `delete=` у:
  - `console` на `<sub>/policy` (`:8`), `platform/servers/<сервер>` (`:9`), `door/signer` (`:17`), `door/keys` (`:18`), `<sub>/next_id` (`:20`), `platform/schema` (`:44`), `<sub>/sweep` (`:49`);
  - `<s>worker` на `<sub>/slots/<имя>` (`:22`), `<sub>/epoch/<id>` (`:23`), `<sub>/holds/<место>` (`:26`), `<sub>/requests/<rid>` (`:30`), `<sub>/<spec:tables>/<имя>` (`:50`);
  - `resource` на `platform/doors/<сервер>` (`:10`).
- В результате по `catalog.tsv` невозможно отличить `objects/<sub>/commands/<rid>` (`:33`, где у `console` в `configstore-rights.json` действительно нет `delete`) от `<sub>/policy` (`:8`) или `<sub>/next_id` (`:20`), где у `console` в `configstore-rights.json` `delete` есть.

### 3. Межподсистемные и спековые правила из `М10/6 Н1.4`, не выразимые через строки `catalog.tsv`
- **`<s>controller` (`06-rights.norms.md:132`):** получает `read` на `<другая>/*, !<другая>/idem/*, !<другая>/asked/*` для всех спек `<другая>`, на которые `<s>` ссылается через `about.sub`, `near.sub` или `ref`. В `catalog.tsv` в `readers` фигурирует только собственный `<s>controller`.
- **`<s>worker` (`06-rights.norms.md:133, 140`):**
  - при `about.sub` читает `<about.sub>/<rows>/*`;
  - при `worker.reads` и `secrets.reads` читает перечисленные там ключи и префиксы (включая чужие подсистемы);
  - при `worker.requests` (правила R8–R9, `v2-requests`) читает `<t>/requests/*` и `objects/<t>/commands/*` целевой спеки `<t>` только если `<t>` объявила `requests`;
  - по правилу R11 для собираемой книги (`domain.books` с `from`) получает только `delete: <s>/<from>/*` без `write`, если `from` — таблица консоли, тогда как `catalog.tsv:78–79` записывает `guard=<s>worker(...)` (что означает право `write`).
- **`secrets.readers` (`06-rights.norms.md:139–141`, `v5-secret-domainworker`):** динамически добавляет `read` названным ролям и отрицание `!<ключ>` всем остальным ролям, чьи широкие префиксы покрывают секретный ключ. В `catalog.tsv` нет механизма порождения отрицаний из `secrets.readers`.

### 4. Прямые расхождения между конкретными строками `catalog.tsv` и таблицей `М10/6 Н1.4`
| Строка `catalog.tsv` | Ключ в `catalog.tsv` | Что в `catalog.tsv` | Что в `М10/6 Н1.4` и эталонах `06/variants/*` |
|---|---|---|---|
| `:17`, `:18` | `door/signer`, `door/keys` | `when = door.routes` | Выдаются `console` (и `read` воркеру/ресурсу на `door/keys`, `!door/signer` остальным) **безусловно** (`06-rights.norms.md:131, 133, 134`, `v1-base/expect.tsv:6`, `06/scenarios.tsv:53`). |
| `:20`, `:26`, `:49` | `<sub>/next_id`, `<sub>/holds/<место>`, `<sub>/sweep` | `when = unit.id`, `when = placement.places`, `when = unit.fields` | Выдаются `console` (`next_id`, `sweep`) и `<s>worker` (`holds/*`) **безусловно** для каждой спеки (`06-rights.norms.md:131, 133`, `06/scenarios.tsv:5`). |
| `:19` | `<sub>/<spec:unit.rows>/<id>` | `readers` включает `resource` безусловно | По `06-rights.norms.md:134` `resource` получает `read: <s>/<rows>/*` **только у спек с `about`** (`v1-base/expect.tsv:16`: есть `recorders/recorders/*`, нет `cams/cameras/*`). |
| `:23` | `<sub>/epoch/<id>` | `readers = console, <s>controller, <s>worker` | Пропущен `resource`: по `06-rights.norms.md:134` (`<s>/epoch/*`) и `v1-base/expect.tsv:16` `resource` читает `<s>/epoch/*` каждой спеки. |
| `:26`, `:50` | `<sub>/holds/<место>`, `<sub>/<spec:tables>/<имя>` | В `:26` нет `resource`; в `:50` `resource` указан на всех таблицах | По `06-rights.norms.md:134` `resource` читает `<s>/holds/*` и таблицу `events.holds.table`, но не произвольные `tables` спеки. |
| `:34` | `objects/<sub>/<spec:objects.rows>/*` | `readers = <s>worker, resource`; шаблон всегда с `/*` | Пропущен `console` (`06-rights.norms.md:131`: `objects/<s>/<семья>/*`); не отражено правило R10 (`06-rights.norms.md:133`, `v3-objects-rows`): точное имя без `/` даёт образец `objects/<s>/<имя>` без `/*`, а префикс `fam/` при подстановке в шаблон `:34` даёт `objects/<sub>/fam//*`. |
| `:74`, `:75`, `:80–81`, `:95`, `:105` | `domain/grants`, `domain/shared`, `domain/<sub>/<spec:domain.books>[/*]`, `domain/topology`, `domain/member-topology` | `<s>worker` в `readers` безусловно (`:74, 75, 95, 105`) или пропущен (`:80–81`) | По `06-rights.norms.md:133` `<s>worker` читает `domain/grants` только при `door.routes`, `domain/shared` — при `domain.shared` или `scope: scenario`, `domain/topology` и `domain/member-topology` — при `scope: unit`, а `domain/<s>/<книга>` и `domain/<s>/<книга>/*` — при `domain.books`. |
| `:80–84` | `domain/<sub>/*` | `when = domain.books` / `domain.kept`; в `:80` нет `<s>domain` в `ops`; в `:82–83` нет `domainagent` в `ops` | По `06-rights.norms.md:28, 135, 137` роль `<s>domain` создаётся только при `domain.kept` или переносимой книге (`kind: transferable`, `06/scenarios.tsv:65`), пишет и `domain/<s>/<книга>` (`:80`), и `domain/<s>/<книга>/*` (`:81`), а `domainagent` по правилу R3 (`v4-domain-kept`) получает `write` на противоположный образец `domain.kept`. |

---

## Замечания по артефактам стадии A (часть М10)

### 1. Каталог данных `Platform/common/data/catalog.tsv` (строки М10)

#### 1.1. [СУЩЕСТВЕННОЕ] Несогласованное применение операции `guard` и потеря обязательных стражей в строках М10
- **Где:** `Platform/common/data/catalog.tsv:19, 20, 26, 50`
- **Цитата:**
  - `:19`: `create=console(создание единицы); cas=console(PUT/PATCH единицы),<s>controller(mark_unplaced при take_over, cas по прочитанной версии); delete=console(DELETE единицы с cas),<s>controller(placement.unplaced.delete_after, cas по прочитанной версии),<s>worker(worker.deletes, cas по прочитанной версии)`
  - `:20`: `create=console(первая единица с авто-id: "2"); cas=console(счётчик авто-id единицы; сдвиг вверх при ручном id >= next_id)`
  - `:26`: `create=<s>worker(cas "", место свободно); cas=<s>worker(своё место: продление и отпуск)`
  - `:50`: `put=console(POST таблицы: полная строка с CAS по прочитанной версии или пустоте),<s>worker(worker.writes при наличии таблицы в спеке); delete=console(DELETE строки таблицы с cas)`
- **Контрпример / доказательство:**
  1. По решению `decisions/inbox/2026-10-18-каталог-данных-форма.md:28, 47` и ответу Q4 в `decisions/inbox/2026-10-18-каталог-данных-вопросы.md:78–80` («`guard` — запись под стражем, с `cas` или без. Какое сравнение версии, говорит условие участника»):
     - В `:26` (`<sub>/holds/<место>`) полностью потеряно требование `М10_Platform/spec/05-the-worker-under-its-slot.norms.md:292–297` (`Н3 «взять_место»`), что любая запись в `<sub>/holds/<место>` (занятие с `cas=""`, продление и освобождение с `cas=V`) выполняется **под стражем своего слота `<sub>/slots/<имя>`** (`guard=<s>worker(...)`, проверяется сц. 07 в `06-rights.norms.md:451`). В самом `2026-10-18-каталог-данных-форма.md:47` эта строка приведена как образцовый пример операции `guard`.
     - В `:19` (`<sub>/<spec:unit.rows>/<id>`) у `<s>controller` при `delete` по `placement.unplaced.delete_after` пропущено условие стража очереди `<sub>/controller/placement_turn` (`04-the-controller-and-placement.norms.md:295, 385`: «Записи прохода в `slots/*`, `epoch/*`, `unplaced` и удаление неразмещённых единиц идут с `guard` на прочитанную версию `placement_turn`»), тогда как в `:15`, `:22`, `:23` тот же страж `placement_turn` записан как `guard=<s>controller(...)`.
     - В `:19` и `:20` записи `console` в `<sub>/<spec:unit.rows>/<id>` и `<sub>/next_id` при мутациях с `Idempotency-Key` идут под стражем `guard` ключа заявки `<sub>/idem/<ключ>` (`03-units-slots-epochs-lease.norms.md:386, 412, 463`).
  2. В `:50` (`<sub>/<spec:tables>/<имя>`) запись `console` с CAS названа `put=console(POST таблицы: полная строка с CAS...)` вместо `create`/`cas`, что расходится и с `2026-10-18-каталог-данных-форма.md:28` (`put` — запись без проверки версии), и с абзацем «Данные» в `07-secrets-and-sealing.norms.md:14` (`<sub>/<spec:tables>/<имя> (cas)`).
- **Нарушенная норма:** `М10/3 Н3`, `М10/4 Н3`, `М10/5 Н3`, `decisions/inbox/2026-10-18-каталог-данных-форма.md:28, 47`, `decisions/inbox/2026-10-18-каталог-данных-вопросы.md:78–80`.
- **Следствие:** Каталог теряет инвариант fenced-записи для `holds/*` и удаления `unplaced` и смешивает `put`, `cas` и `guard`.

#### 1.2. [СУЩЕСТВЕННОЕ] Ошибки и пропуски в `ops` и `readers` строк М10 (`catalog.tsv:9, 13, 16, 19, 21, 22, 23, 27, 29, 30–34, 44`)
- **Где:** `Platform/common/data/catalog.tsv:9, 13, 16, 19, 21, 22, 23, 27, 29, 30, 31, 32, 33, 34, 44`
- **Цитата и сверка построчно:**
  1. `:9` (`platform/servers/<сервер>`): `ops = put=console(PUT /servers/{server}/labels)`. Пропущено `delete=console(DELETE /servers/{server}/labels)` (`04-the-controller-and-placement.norms.md:220`).
  2. `:13` (`<sub>/decommissioned/<сервер>`): `ops = put=<s>controller(...)`. По `04-the-controller-and-placement.norms.md:554` («`decommissioned/*` пишется с `cas`») должно быть `cas=<s>controller(...)` (или `create`/`cas`).
  3. `:16` (`<sub>/controller/pass`): `readers = console`. Пропущен `<s>worker`: по `04-the-controller-and-placement.norms.md:50` и `03-units-slots-epochs-lease.norms.md:536` воркер читает `<sub>/controller/pass` (`names_given` и `hung_move_after`).
  4. `:19` (`<sub>/<spec:unit.rows>/<id>`), `:21` (`<sub>/idem/<key>`), `:50` (`<sub>/<spec:tables>/<имя>`): в `ops` пропущено перезапечатывание секретных полей при старте консоли (`cas=console`, `07-secrets-and-sealing.norms.md:425–427`) и командой `w2cctl secrets seal` (`cas=admin`, `07-secrets-and-sealing.norms.md:350`). Кроме того, в `:21` условие `cas=console(pending -> готовый ответ; перехват чужой pending старше 30 с при том же отпечатке)` неточно: по `03-units-slots-epochs-lease.norms.md:372` (шаг 3) запись `pending` старше 30 с перехватывается с `cas` независимо от совпадения отпечатка (`при другом отпечатке старый запрос брошен, ключ перехватывается под новый`).
  5. `:22` (`<sub>/slots/<имя>`): в `cas=...,<s>controller(release по судьбе...)` пропущена запись `release` контроллером при выводе сервера (`decommission` / `drain`, `04-the-controller-and-placement.norms.md:375, 546`).
  6. `:23` (`<sub>/epoch/<id>`): `readers = console, <s>controller, <s>worker`. Пропущен `resource` (`06-rights.norms.md:134`, `08-events-resource-requests.norms.md:17, 138`).
  7. `:27` (`<sub>/contenders/<имя>/<коробка>`, `kind = object`): `readers = console, <s>controller, <s>worker`. Объекты в хранилище объектов ресурса контроллер и воркер не читают; их читает только `console` через внутреннюю дверь ресурса при сборке `/status` (`05-the-worker-under-its-slot.norms.md:122`, `09-the-console.norms.md:271`).
  8. `:29` (`platform/resources/<server>/heartbeat`): `readers = console, <s>controller`. Пропущены `resource` (читает пульсы всех известных коробок при старте в `restore`, `11-the-platform-on-a-box-and-a-cluster.norms.md:17, 280`) и `domainagent` (`М11/3 Н1.2`).
  9. `:30` (`<sub>/requests/<rid>`) и `:33` (`objects/<sub>/commands/<rid>`): в `readers` пропущен `<другая>worker` (при `worker.requests`, `06-rights.norms.md:133`, `08-events-resource-requests.norms.md:617–618`); в `:33` в `mark=<s>worker(begun до вызова)` пропущена отметка `no_begun` держателем перед вызовом с `begun: false` (`08-events-resource-requests.norms.md:311–315`).
  10. `:31` (`<sub>/requests/free-<server>-<volume>`): `delete=resource(после чистки тома)`. Пропущен `console`: жнец консоли удаляет просьбу ресурса без живого хозяина по истечении `ttl` (`08-events-resource-requests.norms.md:239, 695`).
  11. `:32` (`<sub>/asked/<sha16(имя)>`): в `delete=console(пустой учёт)` пропущено явное удаление `DELETE /<sub>/asked/{sha16}` в окне обслуживания (`08-events-resource-requests.norms.md:398, 702`).
  12. `:34` (`objects/<sub>/<spec:objects.rows>/*`): `readers = <s>worker, resource`. Пропущен `console` (`06-rights.norms.md:131`).
  13. `:44` (`platform/schema`): `ops = put=console(POST /schema, только вверх)`, `readers = console, <s>controller, <s>worker, resource`. Во-первых, по `10-schema-drain-snapshot-limits.norms.md:204, 240` запись идёт через `create` (когда ключа нет) или `cas` по прочитанной версии, причём допускается и та же версия `version >= cur.version` (сц. 01 `10-schema-drain-snapshot-limits.norms.md:323`). Во-вторых, в `readers` пропущен `domainconsole` (`06-rights.norms.md:136`, `10-schema-drain-snapshot-limits.norms.md:254`).
- **Нарушенная норма:** `М10/3 Н3`, `М10/4 Н1.2, Н2.1, Н3`, `М10/5 Н1.4`, `М10/6 Н1.4`, `М10/7 Н2, Н3`, `М10/8 Н1.3–Н1.5, Н2, Н3`, `М10/10 Н2, Н3`, `М10/11 Н1.4`.
- **Следствие:** При нарезке микромодулей (стадия B) по `catalog.tsv` часть законных читателей и писателей выпадет из таблиц «Данные» целевых уроков.

#### 1.3. [СУЩЕСТВЕННОЕ] Ошибки в строках файлов событий, блобов, запасных воркеров и TLS-ключей (`catalog.tsv:39–42, 47–49, 52, 58`)
- **Где:** `Platform/common/data/catalog.tsv:39–42, 47–49, 52, 58`
- **Цитата и доказательство:**
  1. **Бакеты событий (`:39–42`):**
     - Во всех четырёх строках (`:39–42`) в `ops` указан только `append=...`, но пропущены `delete=resource(удаление закрытых бакетов старше срока хранения retain, М10/8 Н3)` (`08-events-resource-requests.norms.md:112, 600`) и `put=resource(восстановление закрытых бакетов от соседей при старте, М10/11 Н1.4)` (`11-the-platform-on-a-box-and-a-cluster.norms.md:280`).
     - В `:40` (`<корень событий>/<sub>.alarms/<id>/e<эпоха>/<YYYYMMDDTHHMMSSZ>.events.jsonl`) в `append=<s>worker(...)` пропущен `<s>controller`, который пишет тревоги единицы и подсистемы (`hung`, `unsure`, `units.left_on_leaving`, `spares.no_server`, `04-the-controller-and-placement.norms.md:376, 381, 387`).
     - В `:41` (`audit/<роль>/e1/...`) запись `append=console,<s>controller,<s>worker,resource,domain,domainconsole,admin(w2cctl: строка в audit/admin/e1/)` нарушает синтаксис `decisions/inbox/2026-10-18-каталог-данных-форма.md:29` («Несколько участников одной операции — через запятую: `cas=console(PUT единицы),<s>controller(mark_unplaced)`»): у первых шести ролей отсутствуют скобки `(условие)`.
  2. **Блобы и метки удаления (`:47–49`):**
     - В `:47` (`<sub>/blobs/sha256-<hex>`) в `delete=console(жнец по <sub>/sweep)` пропущен `resource`, который удаляет локальную копию блоба при опросе `.gone/` соседей (`10-schema-drain-snapshot-limits.norms.md:135–136`).
     - В `:48` (`<корень объектов>/.gone/<ключ>`) написано `create=console(жнец при удалении блоба: пустой файл-метка); delete=console(после обхода соседей раз в 10 мин, не дольше 7 дней)`. Но по `10-schema-drain-snapshot-limits.norms.md:134–140` обход соседей (`peers`) каждые 10 минут и удаление `.gone/<ключ>` старше 7 дней выполняет **сервис ресурса (`resource`)**, а не `console`.
     - В `:47–49` в колонке `when` указано `unit.fields`, хотя `unit.fields` обязателен в любой спеке (`02-the-spec-and-the-strict-loader.norms.md:38`); условием существования семей блобов является наличие поля с `type: blob` в `unit.fields` или `tables.*.fields` (`10-schema-drain-snapshot-limits.norms.md:107`).
  3. **Файл запасного воркера (`:52`, `/run/w2c-spares/<юнит>.env`):**
     - В `ops` указано `create=admin(w2c-spares.sh по предложению слота с box == BOX_ID)`. Но по `11-the-platform-on-a-box-and-a-cluster.norms.md:48, 303` таймер `w2c-spares.service` работает под отдельным пользователем `w2c-spares` без групп (не `admin`) и перезаписывает файл атомарно через `tmp + rename` (`put`).
  4. **Закрытый ключ TLS роли (`:58`, `/etc/w2c/tls/<роль>/server.key`):**
     - В `readers` указано `*` (все роли!). По `11-the-platform-on-a-box-and-a-cluster.norms.md:73, 335` каталог `/etc/w2c/tls/<роль>` имеет права `0750` (группа `<роль>`), а закрытый ключ `server.key` (`0600` или `0640`) читает только сама `<роль>`, а не `*`.
- **Нарушенная норма:** `М10/4 Н3`, `М10/8 Н1.2, Н3`, `М10/10 Н1.5`, `М10/11 Н1.1, Н1.4–Н1.6`, `decisions/inbox/2026-10-18-каталог-данных-форма.md:29`.
- **Следствие:** Ошибочное распределение обязанностей между `console`, `resource`, `w2c-spares` и `admin` и неверная модель доступа к закрытым TLS-ключам.

#### 1.4. [ЗАМЕЧАНИЕ] Пропущенные в `catalog.tsv` семьи файлов и объектов М10 и расхождение пути каталога в решениях
- **Где:** `Platform/common/data/catalog.tsv:34, 39–42, 113`, `decisions/inbox/2026-10-18-каталог-данных-форма.md:11, 14, 68`, `decisions/inbox/2026-10-18-каталог-данных-вопросы.md:18`
- **Контрпример / доказательство:**
  1. В `catalog.tsv` отсутствуют бакеты тревог `<корень событий>/audit.alarms/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl` и `<корень событий>/console.alarms/<экземпляр>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl`, нормированные в `08-events-resource-requests.norms.md:87, 93–94` и в решении второго пилота Н-2 (`decisions/inbox/2026-10-18-пилот-кластера.md:93–96`).
  2. Отсутствует семья пользовательских объектов двери объектов `<sub>/<spec:objects.door>/*` (`02-the-spec-and-the-strict-loader.norms.md:265`, `08-events-resource-requests.norms.md:38, 53`).
  3. Строка `:113` (`<корень событий>/.workers/<sub>/<экземпляр>.lock`, `owner = М10/8`) помещена в самый конец файла после всех строк `М11/1–12` (`:59–112`), хотя относится к `М10/8` (рядом со строками `:39–43`).
  4. В `decisions/inbox/2026-10-18-каталог-данных-форма.md:11, 14, 68` и `2026-10-18-каталог-данных-вопросы.md:18` путь каталога указан как `Platform/contracts/data/catalog.tsv`, тогда как файл создан по пути `Platform/common/data/catalog.tsv` (по `Platform/module-design.md:36`).
- **Нарушенная норма:** `М10/2 Н1.2а`, `М10/8 Н1.1, Н1.2`, `decisions/inbox/2026-10-18-каталог-данных-форма.md:14`.
- **Следствие:** Неполнота единого источника правды по файлам событий и объектам ресурса.

---

### 2. Абзацы «Данные» в `М10_Platform/spec/01..11-*.norms.md`

#### 2.1. [СУЩЕСТВЕННОЕ] Пропуски читаемых и записываемых ключей в абзацах «Данные» уроков `М10/2`, `М10/3`, `М10/4`, `М10/5`
- **Где:**
  - `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:14–15`
  - `М10_Platform/spec/03-units-slots-epochs-lease.norms.md:17–19`
  - `М10_Platform/spec/04-the-controller-and-placement.norms.md:13–16`
  - `М10_Platform/spec/05-the-worker-under-its-slot.norms.md:13–16`
- **Цитата и сверка с правилом `2026-10-18-каталог-данных-форма.md:88` («процесс или проход урока Н3 не читает и не пишет ключ, которого нет в „Данные“ этого урока»):**
  1. **`02-the-spec-and-the-strict-loader.norms.md:14–15`:** в `читает` указано только `platform/spec/<sub>, platform/spec/<sub>/rev`. Пропущен ключ `platform/schema`, который каждый процесс проверяет на шаге 0 «Старт процесса» (`:471`).
  2. **`03-units-slots-epochs-lease.norms.md:17–19`:**
     - В `читает` пропущены `<sub>/heartbeats/<имя>` (пульс держателя для вычисления `holder` в `GET /<rows>`, `:89, 311` — в `2026-10-18-каталог-данных-форма.md:71` он был в образце для М10/3, но выпал при переносе), `<sub>/<spec:tables>/<имя>` (проверка `ref` и `must_match` в Н3 шаги 7 и 5, `:167, 400, 475`) и `/etc/w2c/secrets/platform.key` (расшифровка `*_secret` перед подсчётом отпечатка заявки, `:366`).
     - Отсутствует пункт `пишет:` для `<sub>/<spec:domain.books.from>/<слот> (delete)` (очистка прежних строк собираемых книг на переходе `claimed -> active` в Н3 «захватить» шаги 4–5, `:554`) и `audit/<роль>/e1/… (append)` (запись `next_id.recovered`, `:417`).
  3. **`04-the-controller-and-placement.norms.md:13–16`:**
     - В `пишет` для слотов указано только `<sub>/slots/<имя> (create)`, но контроллер в этом же уроке пишет `<sub>/slots/<имя> (cas)` (`release` по судьбе и при выводе сервера, `:473, 546`) и `<sub>/slots/<имя> (delete)` (отзыв непринятых предложений, `:528`), а также пишет тревоги в `<корень событий>/<sub>.alarms/<id>/e<эпоха>/<YYYYMMDDTHHMMSSZ>.events.jsonl (append)` и аудит в `<корень событий>/audit/<роль>/e1/<YYYYMMDDTHHMMSSZ>.events.jsonl (append)` (`:376, 381, 387`).
     - В `читает` пропущены `<sub>/<spec:unit.rows>/<id>` (читается на шаге 1 каждого прохода контроллера, `:322, 372`), `<sub>/<spec:tables>/<имя>` (таблицы `places.table` и `affinity.table`, `:91, 96`) и `platform/spec/<sub>/rev` (`:374`).
  4. **`05-the-worker-under-its-slot.norms.md:13–16`:**
     - В `читает` пропущены `<sub>/slots/<имя>`, `<sub>/epoch/<id>`, `<sub>/controller/pass` (`names_given`, `hung_move_after`), `<sub>/decommissioned/<сервер>` (проверяется наравне с `platform/decommission/<сервер>` в Н3 шаг 3, `:253`), `<sub>/<spec:tables>/<имя>` (`places.table`, `:292`), `platform/spec/<sub>/rev` (`:247`).
     - В `пишет` пропущены бакеты событий `<sub>/… (append)`, `<sub>.alarms/… (append)` и `audit/… (append)` (`:282, 314`).
- **Нарушенная норма:** `decisions/inbox/2026-10-18-каталог-данных-форма.md:62–88`, `М10/2 Н3`, `М10/3 Н3`, `М10/4 Н3`, `М10/5 Н3`.
- **Следствие:** Абзацы «Данные» уроков 02–05 не замкнуты относительно шагов `Н3` тех же уроков.

#### 2.2. [СУЩЕСТВЕННОЕ] Пропуски читаемых и записываемых ключей в абзацах «Данные» уроков `М10/7`, `М10/8`, `М10/9`, `М10/10`, `М10/11`
- **Где:**
  - `М10_Platform/spec/07-secrets-and-sealing.norms.md:12–15`
  - `М10_Platform/spec/08-events-resource-requests.norms.md:14–17`
  - `М10_Platform/spec/09-the-console.norms.md:12–15`
  - `М10_Platform/spec/10-schema-drain-snapshot-limits.norms.md:14–17`
  - `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:14–17`
- **Цитата и доказательство:**
  1. **`07-secrets-and-sealing.norms.md:12–15`:** в `пишет` пропущен `<sub>/idem/<key> (cas)` (перезапечатывание секретов в заявках при старте консоли, `:425–427`, хотя в `читает` `<sub>/idem/<key>` включён); в `читает` пропущены `door/signer` и `<sub>/<spec:tables>/<имя>`.
  2. **`08-events-resource-requests.norms.md:14–17`:** в `читает` пропущены `<sub>/<spec:unit.rows>/<id>` (проверка существования единицы и `about.field` при подаче просьбы и чтении событий, `:367, 639`), `platform/doors/<сервер>` (кольцо соседей ресурса и опрос ресурсов консолью; есть только в `пишет`, `:45, 591`), а во `владеет` пропущены `audit.alarms` и `console.alarms` (`:93–94`).
  3. **`09-the-console.norms.md:12–15`:** в `пишет` пропущены `platform/servers/<сервер> (delete)` и `audit/console/e1/… (append)`; в `читает` пропущены ключи, которые консоль читает при сборке `/status`, `/servers` и в доменной сторожевой (`Н1.1`, `Н2`, `Н3`): `<sub>/workers/<имя>`, `<sub>/contenders/<имя>/<коробка>`, `<sub>/<spec:tables>/<имя>`, `<sub>/snapshot/unplaced`, `<sub>/decommissioned/<сервер>`, `platform/servers/<сервер>`, `platform/drain`, `platform/decommission/<сервер>`, `<sub>/policy`, `platform/schema`, `/etc/w2c/secrets/platform.key`, `domain/keys`, `domain/root`, `domain/grants`, `domain/disabled`, `domain/revoked`, `domain/break-glass/<кластер>`, `domain/member`, `domain/member-list`, `domain/holder`.
  4. **`10-schema-drain-snapshot-limits.norms.md:14–17`:** в `пишет` указано только `platform/drain (put)`, пропущен `platform/drain (delete)` (`DELETE /drain`, `:205`) и `audit/console/e1/… (append)`; в `читает` пропущены `platform/drain`, `<sub>/holds/<место>` (вычисление `held_by` в `GET/POST /<table>`, `:177`), `platform/doors/<сервер>` (список соседей для зеркалирования блобов, `:128`), `/etc/w2c/secrets/platform.key` (маскирование и вырезание секретов в снимке, `:62`).
  5. **`11-the-platform-on-a-box-and-a-cluster.norms.md:14–17`:** в `пишет` пропущены `platform/spec/<sub> (put)`, `platform/spec/<sub>/rev (create, cas)` (`install.sh` / `w2cctl spec put`, `:358, 391`), `platform/mirror (put)`, `platform/space (put)`, `<sub>/retention (put)`, `<sub>/alarms_retention (put)` (`w2cctl`, `:388–392`) и файлы бакетов событий при `restore` от соседей (`:280`); в `читает` пропущены `platform/epoch_floor` и `<sub>/epoch/<id>` (расчёт `upper` в `restore`/`import`, `:201, 461`), `.workers/<sub>/<экземпляр>.lock` (`:291`), `.mirror/<server>/…` (`:280`) и `platform/schema` (`:439`).
- **Нарушенная норма:** `decisions/inbox/2026-10-18-каталог-данных-форма.md:62–88`, `М10/7 Н3`, `М10/8 Н1.2, Н3`, `М10/9 Н1.1, Н3`, `М10/10 Н1.5, Н2, Н3`, `М10/11 Н1.4, Н1.7, Н2, Н3`.
- **Следствие:** Неполная сверка «Данные» ↔ `Н3` в пяти уроках М10.

---

### 3. Карта переноса норм `Platform/common/id-map.tsv` (194 нормы М10)

#### 3.1. [СУЩЕСТВЕННОЕ] Ошибочная глава в `note` у `М10/7-07` (`2.4` вместо `2.1, 4`)
- **Где:** `Platform/common/id-map.tsv:133`
- **Цитата:** `М10/7-07	P/06.2-04	6.2	пароль в адресе, secret_in	2.4 — разбор адреса`
- **Контрпример / доказательство:**
  - Глава `2.4` в `Platform/module-design.md:52, 74` — это «Запуск процесса на коробке: окружение, каталоги, ключи, сокеты, адрес прослушивания» (куда отнесена норма `М10/6-11` о формате сетевого адреса прослушивания демона).
  - Норма `М10/7-07` (`07-secrets-and-sealing.norms.md:528`: «Пароль в адресе, `credentials`, `secret_in`: разделы Н1.3, Н2, Н3 и таблица `secret_in.tsv`») регулирует:
    1. Запрет пароля в URL при приёме на двери консоли (`6.2`).
    2. Разбор ключей спеки `credentials` и `secret_in` строгим загрузчиком (`2.1`, ср. `Platform/module-design.md:140`: `Разбор адреса (secret_in) | 2.1, 6.2`).
    3. Маскирование секретных параметров URL в снимке неразмещённых единиц контроллера (`4`, `10-schema-drain-snapshot-limits.norms.md:65`).
- **Нарушенная норма:** `Platform/module-design.md:70, 74, 140`, `М10/7-07`.
- **Следствие:** При переносе норм в стадии B проверка `credentials`/`secret_in` попала бы в урок про systemd-раннер (`2.4`) вместо строгого загрузчика (`2.1`) и контроллера (`4`).

#### 3.2. [СУЩЕСТВЕННОЕ] Потеря требований к раннеру (`2.4`) и запасным воркерам (`2.4, 3.2`) в `М10/11-18`
- **Где:** `Platform/common/id-map.tsv:200`
- **Цитата:** `М10/11-18	P/01.3-08	1.3	жизненный цикл: backup, recover	-`
- **Контрпример / доказательство:**
  - В `11-the-platform-on-a-box-and-a-cluster.norms.md:605` норма `М10/11-18` включает три независимых предмета:
    1. «Раннер и грамматика файлов окружения, проверка `W2C_ROLE` против сокета: раздел Н1.2 и сценарии 33–35» → это глава **`2.4`** (`Platform/module-design.md:74`).
    2. «Запасные на коробке (`/run/w2c-spares/`, `w2c-spares.sh`): раздел Н1.5 и сценарий 32» → это главы **`2.4`** и **`3.2`** (`Platform/module-design.md:74, 79`).
    3. «Снимок и восстановление хранилища (`backup`, `restore`, `import`, останов, `FORMAT`): раздел Н1.3 и сценарий 36» → это глава **`1.3`**.
  - При `note = -` первые две части нормы `М10/11-18` (раннер `w2c-run.sh` и `w2c-spares.sh`) полностью выпадают из целевых глав `2.4` и `3.2`.
- **Нарушенная норма:** `М10/11-18` (`11-the-platform-on-a-box-and-a-cluster.norms.md:605`), `Platform/module-design.md:74, 79`.
- **Следствие:** Потеря нормативных требований Н1.2 и Н1.5 и сценариев 32–35 при сборке уроков `2.4` и `3.2`.

#### 3.3. [СУЩЕСТВЕННОЕ] В `М10/8-13` перепутана основная глава (`3.6` вместо `6.4`) и пропущено деление на `2.1`
- **Где:** `Platform/common/id-map.tsv:152`
- **Цитата:** `М10/8-13	P/03.6-02	3.6	подача просьбы воркером, filed	6.4 — дверь просьб`
- **Контрпример / доказательство:**
  - В `08-events-resource-requests.norms.md:830` норма `М10/8-13` («Просьбы воркеров (`POST /<sub>/requests`, `filed`, потолок открытых, слияние по дайджесту, `per_person` и `asked`): разделы Н1.5, Н2, Н3, Н4 и сценарии 04–07, 15, 22») — это прежде всего работа **двери консоли** `POST /<sub>/requests` (проверка схемы, слияние по дайджесту, потолок 1000 открытых, запись `<sub>/requests/<rid>` и `<sub>/asked/<sha16>`, глава **`6.4`**) плюс проверка ключей спеки `requests.*` строгим загрузчиком (глава **`2.1`**, сценарий 22) и лишь в части посылки запроса — воркер (`3.6`).
  - Из-за отнесения `М10/8-13` в `3.6` у главы `6.4` в `id-map.tsv:153–157` остались только нормы про исполнение, отмену и уборку (`P/06.4-01..05`), но нет ни одной первичной нормы `P/06.4-*` про сам приём просьбы `POST /<sub>/requests`, а глава `2.1` не упомянута даже в `note`.
- **Нарушенная норма:** `М10/8-13`, `Platform/module-design.md:70, 96`.
- **Следствие:** В главе `6.4` отсутствует головная норма приёма просьбы, а в `2.1` теряется проверка ключей `requests.*` спеки.

#### 3.4. [ЗАМЕЧАНИЕ] Пустая глава `3.1` в `id-map.tsv` и пропущенные деления (`note`) у сквозных норм М10
- **Где:** `Platform/common/id-map.tsv:96, 99, 101, 106, 120, 136, 162, 167, 178, 185, 192, 199`
- **Контрпример / доказательство:**
  1. В `Platform/module-design.md:53, 78` объявлена глава `3.1 — Договор библиотеки с кодом подсистемы: вызовы старта, шага, смены слота и останова`, но в `id-map.tsv` нет ни одной нормы с `chapter = 3.1` (`P/03.1-*`), а в `note` `3.1` упомянута только у `М10/5-10` (`:106`), но пропущена у `М10/5-03` (`:99`, коды возврата `0`/`1`/`2`) и `М10/5-05` (`:101`, договор вызова при работе под слотом).
  2. Пропущены вторые главы в `note`:
     - `М10/4-20` (`:96`): маршрут `/where/<id>` по `Platform/module-design.md:97` относится к главе `6.5` («Маршруты к воркеру и `/where`»), но в `:96` указаны только `chapter = 4` и `note = 6.6`;
     - `М10/6-07` (`:120`): включает маршрут хранилища `GET /v1/rights` (`1.2`) и отказы загрузчика спеки (`2.1`), но `note = -`;
     - `М10/7-10` (`:136`): включает проверку загрузчиком `secrets.readers`/`secrets.reads` (`2.1`) и проверку прав при чтении (`1.2`), но `note = -`;
     - `М10/9-04` (`:162`): включает проверку доменных ключей сторожевой (`6.7`), но `note = -`;
     - `М10/9-09` (`:167`): включает проверку токена двери воркером (`3.4`) и двойное чтение `intent` с контроллером (`4`), но `note = -`;
     - `М10/10-06` (`:178`): по `Platform/module-design.md:100` таблица потолков делится между `2.1`, `3.6`, `5.1`, `6.1`, `6.2`, `6.4`, но в `note` указаны только `5.1, 6.1, 6.4`;
     - `М10/11-03` (`:185`): включает правило `READY=1` для воркера (`3.2`) и контроллера (`4`), но в `note` указаны только `1.3, 5.1, 6.1`;
     - `М10/11-10` (`:192`): включает старт запасного воркера (`3.2`) и проверку бюджета памяти воркером (`3.4`), но в `note` указана только `2.3`;
     - `М10/11-17` (`:199`): включает отказ `503` на `door.pass` без живого воркера (`6.5`), но `note = -`.
- **Нарушенная норма:** `Platform/module-design.md:53, 78, 97, 100`.
- **Следствие:** Неполная трассировка сквозных норм при разрезании монолитных уроков М10 на микромодули.

---

### 4. Векторы (`Source/tests/testdata/*.tsv`, `request-digest`, `rights-evaluator`, `Platform/common/vectors/README.md`)

#### 4.1. [СУЩЕСТВЕННОЕ] Вектор `Source/tests/testdata/requests_body.tsv` противоречит нормам `М10/8` и `М10/3` по кодам `fault` и маршруту
- **Где:** `Source/tests/testdata/requests_body.tsv:7, 19, 35, 105–109, 111`
- **Цитата:**
  - `:7`: `# Write side: POST /<rows> and PUT/PATCH /<rows>/{id} (М10/03), POST /<table> (М10/10), POST /requests (М10/08).`
  - `:19`: `number	1e400		not_number	IEEE 754 overflow (Infinity) rejected`
  - `:105`: `request	not json		not_json	request body must be JSON object`
  - `:106`: `request	{"title":1e400}		not_number	non-finite number inside request rejected`
  - `:108`: `json	{"x":1e400}		not_number	non-finite number inside json field rejected`
- **Контрпример / доказательство:**
  1. **Неверный `fault` у `field = request` (`:105–107, 109, 111`):** по `08-events-resource-requests.norms.md:411–412, 741` и `08-events-resource-requests.api.openapi.yaml` схема `RequestError` на `POST /<sub>/requests` содержит `fault: "too_long"` **только** при превышении длины строкового поля просьбы; при не-JSON теле или нарушении схемы возвращается `400 RequestError` **без поля `fault`**. Это прямо проверено в `Source/tests/testdata/acceptance/М10_Platform/08/scenarios.tsv:81` (`POST /cams/requests` с не-JSON телом → `400` и `"fault": "@absent"`).
  2. **Неверный `fault` для `1e400`/`1e999` (`:19, 35, 106–108`):** по `03-units-slots-epochs-lease.norms.md:364–365, 651–652, 719` («Число вне диапазона IEEE 754 double (`1e400`, `-1e400`) при разборе JSON-тела — `400` с `fault: not_json`») и `Source/tests/testdata/acceptance/М10_Platform/03/scenarios.tsv:47` (`1e400` → `fault: "not_json"`) переполнение `float64` отвергается на этапе разбора JSON-тела с `not_json`, а не `not_number` (тем более для поля типа `json` в `:108`, где проверка типа поля — объект/массив, а не число).
  3. **Неверный маршрут в шапке (`:7`):** указан короткий `POST /requests`, хотя по `08-events-resource-requests.norms.md:400–401` и `09-the-console.norms.md:235` у `/<sub>/requests` нет короткого маршрута и `POST /requests` возвращает `404`.
- **Нарушенная норма:** `М10/3 Н3, Н4, Н5` (`03-units-slots-epochs-lease.norms.md:364, 651, 719`), `М10/8 Н2, Н4` (`08-events-resource-requests.norms.md:400, 411, 741`).
- **Следствие:** Реализация, проходящая приёмочные сценарии `03/scenarios.tsv:47` и `08/scenarios.tsv:81`, упадёт на `requests_body.tsv`, и наоборот.

#### 4.2. [СУЩЕСТВЕННОЕ] Вектор `Source/tests/testdata/group_of.tsv` противоречит `М10/2 Н1.2а`, `М10/3 Н4` и `М10/4 Н1.3`
- **Где:** `Source/tests/testdata/group_of.tsv:21–23, 31–36, 46, 49, 65–66, 72–74, 83, 93, 96, 102, 122–124, 141, 149, 151, 154, 161, 164, 166–169` (и `Source/tests/testdata/secret_in.tsv:403`)
- **Цитата:**
  - `group_of.tsv:21`: `driverpack://acme	path	acme	`
  - `group_of.tsv:22`: `driverpack://acme/	path	acme	`
  - `group_of.tsv:31`: `http://10.0.0.1/a b	authority	10.0.0.1	bad_url`
  - `group_of.tsv:167`: `rtsp://cam.local/live^1	authority	cam.local	bad_url`
- **Контрпример / доказательство:**
  1. **Схемы с `host: path` без сегмента пути (`:21–23, 74, 83, 93, 149, 151, 161` и `secret_in.tsv:403`):** по `02-the-spec-and-the-strict-loader.norms.md:170` («при `host: path` узел `authority` — не хост; хост — первый непустой сегмент пути после `/`, и он ДОЛЖЕН быть») и `03-units-slots-epochs-lease.norms.md:665` («при `host: path` пути нет — места хоста нет: `mirror://local` — `bad_url`») адреса `driverpack://acme`, `driverpack://acme/`, `driverpack://file`, `mirror://acme`, `mirror://hub1` не имеют первого сегмента пути и обязаны отвергаться с `fault = bad_url` и пустой группой, однако в `group_of.tsv` они имеют пустой `fault` и группу из `authority`.
  2. **Ненулевая группа при `fault = bad_url` (`:31–36, 46, 49, 65–66, 72–73, 96, 102, 122–124, 141, 154, 164, 166–169`):** по `04-the-controller-and-placement.norms.md:93` («Значения нет, оно пустое или не читается (у `url` — нечитаем по уроку 3 Н4) … — единица не в группе и размещается одна») нечитаемый по уроку 3 Н4 URL (`fault = bad_url`) не образует группы (`group_of = ""`), тогда как `group_of.tsv` требует одновременно `fault = bad_url` и непустую группу.
- **Нарушенная норма:** `М10/2 Н1.2а` (`:170`), `М10/3 Н4` (`:665`), `М10/4 Н1.3` (`:93`).
- **Следствие:** Две разные трактовки `host: path` и `cut_at: host` между текстом норм и таблицей векторов.

#### 4.3. [СУЩЕСТВЕННОЕ] Рассинхронизация `Source/tests/testdata/log_mask.tsv` и `Source/tests/testdata/spec_verdicts.tsv` с таблицами приёмки `М10/7` и `М10/2`
- **Где:** `Source/tests/testdata/log_mask.tsv:1–30`, `Source/tests/testdata/spec_verdicts.tsv:1–145`
- **Цитата:**
  - `spec_verdicts.tsv:4`: `# The cases are byte for byte the same-named cases of acceptance М10/02 (cases/), the verdicts its verdicts.tsv.`
- **Контрпример / доказательство:**
  1. В `Source/tests/testdata/log_mask.tsv` 24 строки данных, тогда как в `Source/tests/testdata/acceptance/М10_Platform/07/log_mask.tsv` — 27 строк данных. В общем векторе потеряны 3 строки (`acceptance/.../07/log_mask.tsv:30, 33, 34`), включая обязательные по `07-secrets-and-sealing.norms.md:117–118, 131–132, 530–532` векторы на **S4** (`rtsp://10.0.0.1/live?pwd=Hun<ter2&x=1` → `rtsp://10.0.0.1/live?pwd=***&x=1`) и **S17** (`rtsp://10.0.0.1/live?%26p%2577d=hunter2` → `rtsp://10.0.0.1/live?***`).
  2. В `Source/tests/testdata/spec_verdicts.tsv` всего **138** кейсов, тогда как в `Source/tests/testdata/acceptance/М10_Platform/02/verdicts.tsv` (на который ссылается `02-the-spec-and-the-strict-loader.norms.md:835`) — **439** кейсов. В `Source/tests/testdata/spec_verdicts.tsv` отсутствуют 301 кейс из `acceptance/М10_Platform/02/verdicts.tsv`.
- **Нарушенная норма:** `М10/2 Н5`, `М10/7 Н1.4, Н5`, `Platform/module-design.md:130, 141`.
- **Следствие:** Общие векторы `Source/tests/testdata/log_mask.tsv` и `spec_verdicts.tsv` не покрывают значительную часть приёмочного набора `М10/2` и `М10/7`.

#### 4.4. [ЗАМЕЧАНИЕ] Пропуск поля `filed` в формуле дайджеста просьбы в `М10/8 Н1.5` при наличии его в векторе `request-digest` и опечатка в примечании `digest.tsv:23`
- **Где:** `Platform/06-console/vectors/request-digest/README.md:31`, `Platform/06-console/vectors/request-digest/digest.tsv:7, 23, 26`, `М10_Platform/spec/08-events-resource-requests.norms.md:274–275`
- **Цитата:**
  - `08-events-resource-requests.norms.md:274–275`: `Дайджест считается от канонического JSON (урок 1 Н1.5) тела без unit, valid_until и штампов: первые 16 hex SHA-256.`
  - `Platform/06-console/vectors/request-digest/README.md:31`: `от канонического JSON (RFC 8785, [М10/1] Н1.5) тела просьбы без полей unit, valid_until, filed и серверных штампов`
  - `digest.tsv:23`: `utf8_note	{"unit":"т1","note":"ж <&>"}	{"note":"ж <&>"}	01417d9c205bd084	UTF-8 as is, U+2028 raw, no HTML escaping`
- **Контрпример / доказательство:**
  - В `digest.tsv:7, 26` (`strip_stamps`, `merge_same_digest`) входное тело содержит клиентское поле `"filed":true`, и вектор выбрасывает `filed` перед хешированием (оставляя `{"action":"reboot"}` → `db50e6c788a1e72b`). Однако в `08-events-resource-requests.norms.md:274–275` (`Н1.5`) среди исключаемых полей названы только `unit, valid_until и штампов` (`filed` — булев признак, а не штамп времени).
  - В `digest.tsv:23` примечание гласит `U+2028 raw`, но во входном JSON `{"unit":"т1","note":"ж <&>"}` символа `U+2028` нет.
- **Нарушенная норма:** `М10/8 Н1.5` (`08-events-resource-requests.norms.md:274–275`).
- **Следствие:** Разночтение между текстом нормы `М10/8 Н1.5` и вектором `request-digest` по исключению поля `filed`.

#### 4.5. [ЗАМЕЧАНИЕ] Неполный перечень общих векторов в `Platform/common/vectors/README.md` и отсутствие шапки владельца/колонок в `secret_in.tsv`
- **Где:** `Platform/common/vectors/README.md:11–26`, `Source/tests/testdata/secret_in.tsv:1–19`
- **Контрпример / доказательство:**
  1. В `Platform/common/vectors/README.md:11–26` перечислены 9 файлов `Source/tests/testdata/*.tsv`, но отсутствуют ещё 6 общих векторов из таблицы `Platform/module-design.md:134, 137, 144, 145, 147, 158`: `Приведение типов (values_by_type)`, `Формат id события`, `Вывод прав из спеки` (`acceptance/М10_Platform/06/variants/`), `Разбор адреса`, `Конверт секрета enc:v2 и кольцо`, `Принять консолью`.
  2. В `Source/tests/testdata/secret_in.tsv:1–19` отсутствует строка `# Owner: «Спецификация»` (требуемая `Platform/module-design.md:41` и присутствующая во всех остальных 8 файлах) и строка с именами колонок `url	host_from	secret_in	cred_names	fault`.
- **Нарушенная норма:** `Platform/module-design.md:41, 128–160`.
- **Следствие:** Неполный индекс общих векторов в `Platform/common/vectors/README.md`.

---

### 5. Файлы жизненного цикла `Platform/0[1-6]-*/lifecycle.md`

#### 5.1. [СУЩЕСТВЕННОЕ] Противоречие `Type=simple` vs `Type=notify` у воркера и тупик готовности запасного воркера
- **Где:** `Platform/03-worker/lifecycle.md:19, 75`, `Platform/01-store/lifecycle.md:85`, `М10_Platform/spec/11-the-platform-on-a-box-and-a-cluster.norms.md:44, 60`
- **Цитата:**
  - `Platform/03-worker/lifecycle.md:19`: `| Type | simple |`
  - `Platform/03-worker/lifecycle.md:75`: `Если задан NOTIFY_SOCKET, воркер шлёт READY=1 после захвата имени и старта пульса (Type=notify) и WATCHDOG=1 на каждом проходе не реже чем раз в WatchdogSec / 2`
  - `Platform/01-store/lifecycle.md:85`: `контроллер и воркер — тоже Type=notify`
- **Контрпример / доказательство:**
  - В `03-worker/lifecycle.md:19` написано `Type = simple`, а в `:75` того же файла, в `01-store/lifecycle.md:85` и в решении второго пилота (`decisions/inbox/2026-10-18-пилот-кластера.md:126`) — `Type=notify` (это же внутреннее противоречие есть в `11-the-platform-on-a-box-and-a-cluster.norms.md:44` vs `:60`).
  - Более того, если у юнита воркера `Type=notify`, а `READY=1` посылается «после захвата имени» (`03-worker/lifecycle.md:75`), то запасной воркер `<dep>-<sub>worker-spare@.service` (или воркер без свободного слота, `05-the-worker-under-its-slot.norms.md:235`) входит в рабочий цикл без имени в ожидании предложения и никогда не пошлёт `READY=1`, из-за чего systemd убьёт его по `TimeoutStartSec`.
- **Нарушенная норма:** `М10/11 Н1.1` (`:44, 60`), `М10/5 Н3`, `decisions/inbox/2026-10-18-пилот-кластера.md:126`.
- **Следствие:** Неоднозначный `Type` systemd-юнита воркера и зависание старта запасного воркера при `Type=notify`.

#### 5.2. [СУЩЕСТВЕННОЕ] Внутренние противоречия в `Platform/06-console/lifecycle.md` по выбору `BOX_ID` и расположению `SECRETS_KEY`
- **Где:** `Platform/06-console/lifecycle.md:39, 85, 91, 93`
- **Цитата:**
  - `:39`: `| BOX_ID | — | /etc/machine-id, иначе короткий hostname |`
  - `:93`: `Консоль без BOX_ID берёт короткое имя хоста: так велит [М10/11] Н1.2`
  - `:85`: `SECRETS_KEY — кольцо стенда вне {data}`
  - `:91`: `Кольцо секретов стенд кладёт в {data}/etc/secrets/platform.key и передаёт через SECRETS_KEY`
- **Контрпример / доказательство:**
  1. Строка `:93` прямо противоречит строке `:39` и норме `11-the-platform-on-a-box-and-a-cluster.norms.md:104`: при пустом `BOX_ID` процесс сначала читает `/etc/machine-id` (без перевода строки), и только если файла нет или он пуст — берёт короткое имя хоста (`hostname` до первой точки).
  2. Строка `:85` («вне `{data}`») прямо противоречит строке `:91` («в `{data}/etc/secrets/platform.key`») и решению второго пилота Н-4 (`decisions/inbox/2026-10-18-пилот-кластера.md:107–115`).
- **Нарушенная норма:** `М10/11 Н1.2` (`:104`), `decisions/inbox/2026-10-18-пилот-кластера.md:107–115`.
- **Следствие:** Прямые противоречия внутри одного документа `06-console/lifecycle.md`.

#### 5.3. [СУЩЕСТВЕННОЕ] Неточности в `Platform/01-store/lifecycle.md` относительно `М10/11 Н1.3` и решений первого пилота
- **Где:** `Platform/01-store/lifecycle.md:18, 26, 33–36, 47, 49, 51`
- **Цитата:**
  - `:18`: `Режим memory:// — встроенный двойник для приёмки и стендов в процессе: файловая система и systemd не задействованы; вся коробка — одна реализация.`
  - `:26`: `| Флаги | -listen, -data, -rights, -roles-dir, -tls, -tuning, -election-timeout, -heartbeat-interval, -snapshot-threshold, -peers |`
  - `:36`: `| CONFIGSTORE_TUNING | -tuning | lan | профиль таймингов: lan (в продакшене) или fast (стенд) |`
  - `:47`: `| /run/configstore/<роль>.sock | сокет роли | 0660 | w2c-store:<роль> |`
  - `:49`: `| /etc/w2c/tls/configstore/ | mTLS-комплект для плота и двери без голоса (-tls) |`
  - `:51`: `Строки хранилища, которыми владеет урок: platform/configstore/members (<id> -> <peer_url>) и platform/decommission/<сервер>`
- **Контрпример / доказательство:**
  1. В `:18` смешаны два разных профиля из `М10/1 Н1.1` и `decisions/inbox/2026-10-18-пилот-хранилища.md:20–24` (А1): `memory://` («в процессе») и `file://` («вся коробка — одна реализация»).
  2. В `:26` и `:33–36` не выписаны типы и умолчания закрытой таблицы флагов демона (`11-the-platform-on-a-box-and-a-cluster.norms.md:238–265`, решение пилота А3 `2026-10-18-пилот-хранилища.md:34–40`), а для `-tuning` указано `lan` (значение из `configstore.env`), тогда как умолчание самого флага `-tuning` по `11-the-platform-on-a-box-and-a-cluster.norms.md:247` — `default` (`election=1000ms`, `heartbeat=100ms`).
  3. В `:47` пропущено правило `11-the-platform-on-a-box-and-a-cluster.norms.md:159` и решения пилота А10 (`2026-10-18-пилот-хранилища.md:78–83`): при запуске без `sd_listen_fds` демон сам создаёт `<roles-dir>/<роль>.sock` с правами `0660` и **группой процесса демона** (а не группой `<роль>`).
  4. В `:49` флаг `-tls` привязан к `/etc/w2c/tls/configstore/`, хотя по `11-the-platform-on-a-box-and-a-cluster.norms.md:246, 333` флаг `-tls` принимает корневой каталог `/etc/w2c/tls`, внутри которого лежат два отдельных комплекта: `configstore/` и `configstore-door/`.
  5. В `:51` среди собственных строк хранилища пропущена `platform/epoch_floor` (`catalog.tsv:24`, `11-the-platform-on-a-box-and-a-cluster.norms.md:201`).
- **Нарушенная норма:** `М10/1 Н1.1`, `М10/11 Н1.3, Н1.6`, `decisions/inbox/2026-10-18-пилот-хранилища.md` (А1, А3, А10).
- **Следствие:** Расхождения контракта запуска демона `w2c-store` с закрытой таблицей флагов `М10/11 Н1.3` и решениями первого пилота.

#### 5.4. [ЗАМЕЧАНИЕ] Пропуски в `Platform/0[2-5]-*/lifecycle.md` и отсутствие порядка приоритета env-файлов в `01`, `03`, `05`, `06`
- **Где:** `Platform/02-installer/lifecycle.md:21–26, 51, 68`, `Platform/03-worker/lifecycle.md:20, 22, 34–46`, `Platform/04-controller/lifecycle.md:24–40, 55–58`, `Platform/05-resource/lifecycle.md:19–20, 53–56`
- **Контрпример / доказательство:**
  1. **`02-installer/lifecycle.md`:** в `:51` пропущен отказ установки (`≠ 0`), если `/etc/<sub>` уже существует как настоящий каталог, а не симлинк (`11-the-platform-on-a-box-and-a-cluster.norms.md:360`, сц. 26); в `:21–26` пропущены `w2cctl status [-rights]` и `w2c-run.sh`; в `:68` сказано «Код выхода `≠ 0` — при недоступном хранилище или отсутствии `roles/<роль>.env`», хотя по `11-the-platform-on-a-box-and-a-cluster.norms.md:308` при отсутствии `roles/<роль>.env` для одной подсистемы `w2c-spares.sh` пропускает только эту роль и продолжает обход остальных.
  2. **`03-worker/lifecycle.md`:** в `:20, 22` описан только выбор по `WORKER_NAME` и в порядке `unit.slots`, но пропущены ветви `SLOT_INDEX` (индекс с 0 в `unit.slots`) и `SPARE_FOR` (перехват конкретного слота запасным) из `05-the-worker-under-its-slot.norms.md:235`; перепутан порядок старта (`экземпляр` поставлен до `бюджет памяти`, тогда как в `11-the-platform-on-a-box-and-a-cluster.norms.md:467–481` шаг 3 — бюджет памяти, а шаг 4 — замок экземпляра); в таблице окружения (`:34–46`) пропущена переменная `BUILD`.
  3. **`04-controller/lifecycle.md`:** в таблице окружения (`:24–38`) отсутствует `RESOURCE_ROOT` / `EVENTS`, хотя в `:58` контроллер пишет в `<корень событий>/audit/<sub>controller/e1/…`; в `:55–57` пропущены чтение `<sub>/epoch/<id>` и работа с `<sub>/controller/placement_turn` и `placement_intent`.
  4. **`05-resource/lifecycle.md`:** в порядке старта (`:19–20`) пропущен шаг 0 — проверка `platform/schema` и чтение спеки до первой записи (`11-the-platform-on-a-box-and-a-cluster.norms.md:439`); в `:53–56` пропущены `platform/spec/<sub>/rev` и запись в `audit/resource/e1/…`.
  5. **Порядок приоритета чтения файлов окружения раннером** (`юнит → roles/<W2C_ROLE>.env → w2c.env → файл подсистемы`, `11-the-platform-on-a-box-and-a-cluster.norms.md:87–97`) выписан только в `04-controller/lifecycle.md:39–40`, но отсутствует в `01-store`, `03-worker`, `05-resource` и `06-console`.
- **Нарушенная норма:** `М10/5 Н3`, `М10/11 Н1.2, Н1.5, Н1.7, Н2, Н3`.
- **Следствие:** Неполнота отдельных `lifecycle.md` при автономном чтении микромодуля.

---

### 6. `НОРМАТИВНЫЕ-СЛОВА.md` и ссылки на него в `Н0`

#### 6.1. [СУЩЕСТВЕННОЕ] В `02-the-spec-and-the-strict-loader.norms.md` (`Н0`) ссылка на нормативные слова осталась вести на `01-storage.norms.md`
- **Где:** `М10_Platform/spec/02-the-spec-and-the-strict-loader.norms.md:6–10`
- **Цитата:**
  ```markdown
  ## Н0. Нормативные слова

  Значение слов `ДОЛЖЕН`, `НЕ ДОЛЖЕН`, `СЛЕДУЕТ`, `НЕ СЛЕДУЕТ`, `МОЖЕТ` — как в [нормах урока 1](01-storage.norms.md), Н0. Непомеченное предложение нормативного раздела читается как `ДОЛЖЕН`.
  ```
- **Контрпример / доказательство:**
  - Во всех остальных 21 файле `*.norms.md` (уроки `М10/1`, `М10/3–11` и `М11/1–12`) раздел `Н0` переведён на `../../НОРМАТИВНЫЕ-СЛОВА.md`, а из `01-storage.norms.md:6–8` таблица нормативных слов удалена.
  - В `02-the-spec-and-the-strict-loader.norms.md:8` ссылка по-прежнему указывает на `01-storage.norms.md`, образуя цепочку косвенной отсылки вопреки `Platform/module-design.md:39, 172` («В Н0 каждого урока остаётся одна ссылка на этот файл») и `НОРМАТИВНЫЕ-СЛОВА.md:4`.
- **Нарушенная норма:** `Platform/module-design.md:39, 172`, `НОРМАТИВНЫЕ-СЛОВА.md:4`.
- **Следствие:** Сломанная прямая ссылка в `Н0` урока `М10/2`.

#### 6.2. [МЕЛОЧЬ] Остаточное дублирование предложения в `М10/3 Н0` и неполное перечисление правил модуля в `НОРМАТИВНЫЕ-СЛОВА.md`
- **Где:** `М10_Platform/spec/03-units-slots-epochs-lease.norms.md:9–10`, `НОРМАТИВНЫЕ-СЛОВА.md:4–5`
- **Цитата:**
  - `03-units-slots-epochs-lease.norms.md:9–10`: `Слова ДОЛЖЕН, НЕ ДОЛЖЕН, СЛЕДУЕТ, НЕ СЛЕДУЕТ, МОЖЕТ — по [НОРМАТИВНЫЕ-СЛОВА.md](../../НОРМАТИВНЫЕ-СЛОВА.md). Непомеченное предложение нормативного раздела читается как ДОЛЖЕН.`
  - `НОРМАТИВНЫЕ-СЛОВА.md:4–5`: `Уроки ссылаются на этот файл из раздела Н0 и добавляют только правила, специфичные для модуля (закрытый мир в М10/1, стабильные коды отказа в М10/2).`
- **Контрпример / доказательство:**
  - В `03-units-slots-epochs-lease.norms.md:9–10` осталась вторая фраза `Непомеченное предложение нормативного раздела читается как ДОЛЖЕН.`, которая уже вынесена в `НОРМАТИВНЫЕ-СЛОВА.md:15` и удалена из `Н0` уроков `01, 04–11`.
  - В `НОРМАТИВНЫЕ-СЛОВА.md:4–5` перечислены только два модульных дополнения (`М10/1` и `М10/2`), но забыто третье правило из `Platform/module-design.md:39, 51` — порядок массивов вывода в `М11/1 Н0`.
- **Нарушенная норма:** `Platform/module-design.md:39, 172`.
- **Следствие:** Мелкая стилевая несогласованность в `Н0`.

# М11/9 — Люди, гранты, имена: нормы

Канон урока. [Лекция](../09-people-grants-names.md), [HTTP-контракт](09-people-grants-names.api.openapi.yaml),
[инструкция](09-people-grants-names.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/09/README.md).

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) (стадия B; урок 8): Н1.1, Н1.2, Н1.3 без `member_copy`/`holder_copy`, Н1.4, Н1.5 `domain`, Н1.6
(строка, `writer`, `GLASS_MIN`, `carry` — сторона держателя), Н1.9 (`first`, `member`), Н1.10, Н2 (строки дверей процесса,
журнал), Н3, Н4 (строки процесса), Н5 (сц. 01, 02, 04, 08, 09, 10). Н1.7 и сц. 05 — [P/08.5](../../Platform/08-domain/spec/08.5-domain.norms.md). Здесь до
переноса уроков 9 и 10 остаются: Н1.3 `member_copy`, `holder_copy` (урок 9); Н1.5 `cluster`, `session`, `body_unit`,
`agent`, Н1.6 `door`, `GLASS_SESSION`, `GLASS_SESSIONS_MAX`, `journal`, Н1.8, Н1.9 `pass` (урок 10, глава 6.7); строки Н2
`GET /domain/grants`, `POST /session/break-glass`, `GET /domain/keys`; строки Н4 `open`, `bad body` у аварийного входа,
`unavailable`; сц. 03, 06 (сц. 07 снят — векторы `common/vectors/may`).

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

**Время.** Поля времени строк и объектов урока — время по [канону Н0](../../Platform/01-store/spec/01.1-store.norms.md#время-в-строке): копия `domain/grants` — `as_of`. Строки держателя (`domain/users/<имя>` — `at`, строка гранта — `until`) — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1 «Время» (стадия B; урок 8).

**Данные** ([каталог](../../Platform/common/data/catalog.tsv)):
- владеет: `domain/grants` (копия у члена);
- читает: `domain/member`, `domain/keys`, `domain/revoked`, `domain/disabled`, `domain/break-glass/<кластер>`.

Строки держателя (`domain/users/<имя>`, `domain/deleting/<имя>`, `domain/disabled`, `domain/grants/<кластер>`,
`domain/break-glass/<кластер>`, запись `domain/revoked`) — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1 «Данные»; `domain/names/<sub>/<книга>` —
[P/08.5](../../Platform/08-domain/spec/08.5-domain.norms.md) (стадия B; урок 8).

Общее уроков 1–8 Н1 действует. Люди живут у держателя; токен человека называет субъект и ничего больше (урок 2 Н1.6,
`kind: person`, без `aud`). Что человеку можно, решает каждый кластер по своим грантам, которые несёт агент; проверка —
локальное чтение без связи с доменом. Люди с паролями и аварийные пароли — операции процесса `domain` (подписант, ADR-0032),
он проверяет каждую сам; гранты пишет он же (урок 3 Н1.8: консоль домена правку передаёт). Решение «Архитектора» по вопросам М11/9.
Абзац перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1 (стадия B; урок 8).

### Н1.1 Человек

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.1 (P/08.4-01; стадия B; урок 8).

### Н1.2 Вход, токен человека, отзыв

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.2 (P/08.4-02, -03; стадия B; урок 8).

### Н1.3 Гранты

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.3 (P/08.4-04; стадия B; урок 8), с абзацами «Окно отзыва» и «Числа заявлены заранее»; здесь
до переноса урока 9 — `member_copy`, `holder_copy` (сторона агента).

```yaml
member_copy:   агент пишет у своего кластера точный ключ domain/grants {doc, as_of} — doc как пришёл, as_of — момент, когда
               держатель собрал ответ: стенные секунды приёма минус domain_age (урок 4; прямой ответ — 0), назад не уходит;
               doc сменился — записать сразу; тот же doc — освежить as_of не чаще FRESH_EVERY (урок 12 Н1.2 fresh); ответ
               из памяти ретранслятора as_of не двигает; поля нет в открывшемся конверте — строку удалить (урок 3 Н1.6
               sealed). Как domain/outcomes
               урока 6: копия члена — точный ключ, строки держателя — семья domain/grants/<кластер>; агенту —
               !domain/grants/* без !domain/grants (P/02.5 Н1.4)
holder_copy:   у кластера держателя копию domain/grants пишет его агент из ответа своего держателя, как у любого члена:
               одно правило чтения, второго писателя нет (ADR-0032); до первого ответа агенту строки нет — прав нет,
               вход — аварийный (Н1.6), как у члена до первого ответа
```

### Н1.4 Право — функция `may`

Вход, вывод и шаги 1–8 — [договор права](../../Platform/common/contracts/may.md) «Функция `may`» (перенесено туда без
изменения; номера шагов прежние; владелец [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.4 (P/08.4-05); исполняют сторожевые P/06.3, 6.7, урок 10 и процесс `domain`;
решение «Архитектора» 2026-10-20, ADR-0083 доп. (14) п. 1; разбор ревью стадии A 8–10). Векторы —
[`common/vectors/may`](../../Platform/common/vectors/may/README.md).

### Н1.5 Сторожевая с грантами

Сторона процесса `domain` (строка `domain`) — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.5 (P/08.4-09; стадия B; урок 8); консоль домена — урок 10.

```yaml
cluster:   P/06.3 Н1.3 identity шаг 3 (Bearer | кука w2c_token): токен — функция token урока 2 по набору и domain/revoked
           этого кластера с expect {kind: person, cluster: null} — договор токена домена «Токен» (решение «Архитектора»
           2026-10-20, ADR-0083 доп. (14) п. 7; разбор ревью стадии A 8–10); отказ — 401 {error: denied, detail:
           "token refused: <слово>"}, форма P/06.3; затем may (Н1.4) с
           grants = doc строки domain/grants (копия этого кластера), as_of — её as_of, disabled — domain/disabled этого
           хранилища (есть только у держателя), cap и unit — need P/06.3 Н1.3; deny — 403 {error: denied, detail:
           "<имя> may not <cap> <sub>/<id> | here"}; stale — detail «the grants this cluster holds are older than a day:
           its agent has not reached the domain»
body_unit: need, чья единица в теле (P/06.3 Н1.3: /marks, POST /<sub>/requests), решается до чтения тела — unit = "*";
           у сторожевой домена действует эта предпроверка до тела, проверки P/06.3 после тела (rights.unit_of, reach,
           names) сохраняются (добавлено сверкой М11)
session:   GET /session доказанной личности (P/06.3 Н1.3) — grants: [{cap, scope}] — действующие строки этого человека
           (шаг 5 may) у этой консоли, по (cap, scope); у аварийной сессии — [] (её may — allow по glass)
loopback:  перенесено в P/06.3 Н1.8 (поздний слой, вводит урок 8.4; стадия B)
agent:     подпись агента своего кластера (урок 3 Н1.4) — двери единиц, как прежде
```

### Н1.6 Аварийный вход

Сторона держателя (строка `domain/break-glass/<кластер>`, `writer`, `GLASS_MIN`, `carry`) — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.6 (P/08.4-08;
стадия B; урок 8); сторона агента в `carry` — урок 9.

```yaml
door:          POST /session/break-glass {who, why, password} у консоли кластера (P/06.3 Н1.3) — по порядку:
               1. консоль open — 400 {error: "open", detail: "this console is open: there is nothing to break into"}
               2. тело не {who, why, password} строками, who или why пусты — 400 bad body
               3. предел Н1.10                                         → 429
               4. нет domain/member — 403 {error: denied, detail: "no emergency account: its store names no member"};
                  нет строки domain/break-glass/<этот кластер> — 403 {error: denied, detail: "no emergency account: …"};
                  не открывается — 503 {error: "unavailable", detail: "the emergency account does not open"}
               5. пароль не сверился — 401 {error: denied, detail: "break-glass: wrong password"} (в счёт предела)
               5а. открытых сессий уже GLASS_SESSIONS_MAX — 429 форма RateLimited контракта P/06 (06-console.api.openapi.yaml), detail «too many
                  emergency sessions», Retry-After — секунды до конца самой ранней сессии; отказ в счёт предела Н1.10
                  не идёт (добавлено сверкой М11, P20)
               6. 200 {user: "break-glass(<who>)", until} + кука w2c_glass; сессия — в памяти процесса консоли,
                  GLASS_SESSION, токена нет
GLASS_SESSION: 900         # с
GLASS_SESSIONS_MAX: 256    # открытых аварийных сессий у консоли; истёкшие не считаются
journal:       access.break_glass.opened {who, why} | .refused {who, why, reason} | .limited; каждое действие под сессией
               сильнее view — access.break_glass {who, method, path}
```

### Н1.7 Индекс имён

Перенесено в [P/08.5 Н1.7](../../Platform/08-domain/spec/08.5-domain.norms.md) (стадия B; урок 8).

### Н1.8 Семьи ключей домена

```yaml
spec:      domain.keys: [{id, keys?: [<ключ>…], prefix?: <семья/>}] — id ^[a-z][a-z0-9_-]{0,31}$ без повторов; хотя бы
           одно из keys, prefix; ключи и семья — под domain/<sub>/; display.keys.<id> — слова только для объявленного id
           (иначе refused:reference); случаи m59_keys_* корпуса P/02.1
door:      GET /domain/keys у консоли кластера (своя, не пересылается; view): {rows, families, keyset}
  rows:      {<ключ строки под domain/>: [<имя поля>…]} — строки этого хранилища, имена полей по возрастанию, без значений;
             строка, чтение которой консоли отказано (P/01.2 Н1.3), пропускается
  families:  {<id>: [<ключ>…]} — по domain.keys спек каталога: названные keys и ключи под prefix, что есть здесь
  keyset:    doc строки domain/keys как есть (открытые ключи) | null
```

### Н1.9 Двери людей и первый администратор

Строки `first`, `member` перенесены в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.9 (P/08.4-07; стадия B; урок 8); передача `pass` — урок 10 (P/10-05).

```yaml
pass:      двери /domain/users… и /domain/break-glass… при любом методе, и GET (разбор ревью стадии A 8–10, № 2), правки
           /domain/grants/… и /domain/revoke консоль домена передаёт процессу domain по уроку 3 Н1.8; процесс проверяет
           токен и domain/grants/domain сам (ADR-0032)
```

### Н1.10 Предел попыток

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н1.10 (P/08.4-06; стадия B; урок 8); счёт `POST /session/break-glass` по тем же правилам — консоль
кластера (урок 10).

---

## Н2 Двери

HTTP-контракт: [09-people-grants-names.api.openapi.yaml](09-people-grants-names.api.openapi.yaml). Тело отказа —
`{error, detail}`. Двери `/domain/*` консоли домена — строки [договора пересылки](../../Platform/common/contracts/forwarding.md) «Двери домена» (добавлено М11/9).

| Дверь | Кто | Право | Успех | Отказы |
|---|---|---|---|---|
| GET `/domain/grants` | консоль домена | view | 200 `{grants: {<кластер>: [line…]}}` | 401/403 |
| POST `/session/break-glass` | консоль кластера | — | Н1.6 | Н1.6, Н1.10 |
| GET `/domain/keys` | консоль кластера | view | Н1.8 | 401/403 |

Строки дверей процесса `domain` (`POST /api/login`, `/domain/users…`, `PUT /domain/grants/<кластер>`, `/domain/break-glass…`,
`POST /domain/revoke`) и абзац «Журнал» перенесены в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н2 (стадия B; урок 8).

---

## Н3 Проход

Перенесено в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н3 («дверь людей», обрыв шага 9, «гранты», «Гонки»; стадия B; урок 8).

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `denied` | 401, 403 | у консолей и дверей людей (форма [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md)): токена нет или не прошёл; `may` — deny; аварийный пароль не сверился (401); нет аварийной учётки (403, `detail` — «no emergency account: …») |
| `too many attempts` | 429 | предел Н1.10, `Retry-After` |
| `unavailable` | 503 | строка аварийной учётки этого кластера не открывается (Н1.6 шаг 4); DELETE человека — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н4 |
| `open` | 400 | аварийный вход у открытой консоли |
| `bad body` у аварийного входа | 400 | `who`, `why` пусты или не строки |

Строки отказов процесса `domain` (`bad body`, `bad name`, `bad password`, `bad line`, `grant too wide`, `refused`, `no such
person`, `exists`, `being deleted`, `unknown subject`, `name taken`, `last admin`, `names unknown`, `too large`, `deposed`,
`standby`) — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н4 (стадия B; урок 8).

Слова `may` — [договор права](../../Platform/common/contracts/may.md) «Слова отказа».

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/09/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/09/README.md)):
стенд урока 5 (`testsub` и `testsub2`) с людьми — сц. 03, 06. Сц. 07 (функция `may`) снят: те же случаи — векторы
[`common/vectors/may`](../../Platform/common/vectors/may/README.md); форма команды `may` и коды выхода — [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) Н5
(стадия B; урок 8). Сц. 01, 02, 04, 08, 09, 10 — [приёмка P/08.4](../../Platform/08-domain/acceptance/4/README.md); сц. 05 —
[приёмка P/08.5](../../Platform/08-domain/acceptance/5/README.md) как 11 (стадия B; урок 8). Отказы загрузки `domain.names` и
`domain.keys` — случаи `m59_*` корпуса P/02.1.

| № | Сценарий | Нормы |
|---|---|---|
| 03 | стенд: аварийный пароль — 400 короткий, 200; вход у `m1`: неверный — 401, верный — сессия, шестая неудача — 429 | Н1.6, Н1.10 |
| 06 | стенд: `GET /domain/keys` у `m1` — строки, семьи `testsub`, набор | Н1.8 |

---

## Решает реализация

Пп. 1–3 перенесены в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) «Решает реализация» (стадия B; урок 8); команда `may` — там же (сц. 07 снят переносом урока 8).

---

## Чеклист готовности

- Пункт М11/9-01 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-01 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/9-02 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/9-03 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/9-04 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-04 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/9-05 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М11/9-06** сторожевая Н1.5: 401/403, `/session` с грантами, консоль домена по `domain/grants/domain` — сц. 01, 02 приёмки P/08.4
- Пункт М11/9-07 перенесён в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) как P/06.3-05 (поздний слой; стадия B; [id-map](../../Platform/common/id-map.tsv)); сценарий 01 остаётся в приёмке М11/09.
- [ ] **М11/9-08** аварийный вход Н1.6 по порядку, сессия 900 с — сц. 03; срок сессии и журнал — чтением (шаг дольше 900 с; журнал приёмка не сравнивает); потолок GLASS_SESSIONS_MAX 256 — чтением (сверка М11, P20); сторона держателя — P/08.4-08
- Пункт М11/9-09 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-06 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/9-10 перенесён в [P/08.5](../../Platform/08-domain/spec/08.5-domain.norms.md) как P/08.5-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М11/9-11** семьи ключей Н1.8 — сц. 06; загрузка — `m59_keys_*`
- Пункт М11/9-12 перенесён в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) как P/08.4-07 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М11/9-13** двери людей через консоль домена к процессу `domain`, проверка там — сц. 01, 02 приёмки P/08.4; проверка у процесса — P/08.4-09

## Соответствие прежним урокам

Нормирует то, что рассказывали `М12A_Domain/04-who-may-call-it.md` (шаг 2 — делегировать власть: токен называет субъект;
шаг 3 — где живут люди и имена; шаг 4 — домен недоступен; шаг 5 — права локальны, их несёт агент, срок — механизм
отзыва; шаг 6 — ворота консоли и двери домена; шаг 7 — аварийный доступ). Токены и подписант — уроки 2 и 7; шаг 1 и «двери
между процессами» — урок 8. Учётки VMS-шлюза (ADR-0074 C5) — пример М12. Лицензия и упаковка `М12A_Domain/05` — М13
(ответ на записку М11 п. 9). ADR-0031, ADR-0032, ADR-0051, ADR-0074 доп. (2). Исторические исходники сохранены в Git. Строка `loopback` Н1.5 и пункт
М11/9-07 перенесены в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) Н1.8, P/06.3-05 (поздний слой; стадия B, урок 6).
Сторона держателя (Н1.1–Н1.4, Н1.5 `domain`, Н1.6 строка, Н1.9 `first`/`member`, Н1.10, Н2–Н5 процесса) и пункты
М11/9-01…05, -09, -12 перенесены в [P/08.4](../../Platform/08-domain/spec/08.4-domain.norms.md) (стадия B, урок 8; абзац о `М12A_Domain/04` — его копия там); Н1.7 и пункт
М11/9-10 — в [P/08.5](../../Platform/08-domain/spec/08.5-domain.norms.md) (стадия B, урок 8).

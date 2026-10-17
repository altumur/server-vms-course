# М11/7 — Токены воркеров через агента: нормы

Канон урока. [Лекция](../07-worker-tokens.md), [HTTP-контракт](07-worker-tokens.api.openapi.yaml),
[инструкция](07-worker-tokens.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/07/README.md).

## Н0 Словарь слов

Нормативные слова — по [общему канону Н0](../../М10_Platform/spec/01-storage.norms.md#н0-словарь-слов).

## Н1 Форма

Общее уроков 2 и 3 Н1 действует. Токен воркера — токен домена урока 2 Н1.6 с `kind` вида спеки. Ключ подписи держателя
воркеру не выдаётся, ключ члена — тоже: токен просит воркер, которому он нужен, через агента своего кластера (ADR-0074
доп. (5)). Токен живёт только в памяти воркера: ни в строке, ни в книге, ни в отчёте, ни в журнале, ни в копии.

### Н1.1 Объявление вида

```yaml
domain.tokens.<вид>:            # раздел спеки (М10/2 Н1.2а); вид ^[a-z][a-z0-9_-]{0,31}$, не person; вид уникален в каталоге
  lifetime:  число > 0, секунды
  claims:    [<имя>…] — непусто, без повторов, без iss, sub, iat, exp, jti, kind
  grant:     [<роль>…] — непусто, без повторов: роли воркеров, которым вид выдаётся
  # область — одна из: placement; unit; placement и unit; scenario один
  placement: {sub, caller, ref_claim, target_fields, audience_claim}
    sub:           подсистема записей назначения (урок 6 Н1.1)
    caller:        cluster | origin | copies — поле записи, где должен стоять член-заявитель
    target_fields: [cluster | origin | copies | centre | star_centre …] без повторов — откуда аудитория
  unit:      {sub?, caller?, ref_claim, target_fields, audience_claim}
    sub?:          подсистема единицы (нет — своя; своя требует domain.ref)
    caller?:       self (умолчание) | poll_home
    target_fields: [poll_home | centre …] без повторов
  scenario:  {doc, items, name, enabled, trigger, target, act, placement?, ref_claim, trigger_claim, acts_claim, up_claim,
              audience_claim}            # требует domain.ref
    doc:           подсистема общего документа (урок 11 Н1.2: shared.<doc>); items — имя массива в нём (одно имя)
    name, enabled, trigger, target, act: пути полей элемента ^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)*$
    placement?:    подсистема, чьи записи назначения называют дом цели
  claims_bind:   ref_claim, audience_claim (у scenario ещё trigger_claim, acts_claim, up_claim) — имена из claims, разные
computed:   centre, star_centre, poll_home — не поля записи и не поля единиц: вычисляются по топологии (урок 4 Н1.2)
            centre — topology.centre; star_centre — centre, если cluster записи в star, иначе ничего;
            poll_home(член) — via[член], иначе centre, иначе держатель
refusals:   отказ загрузки refused:value с путём (М10/2 Н4) на каждое нарушение выше; вид в двух спеках каталога — refused:catalogue
```

### Н1.2 Местная дверь агента

```yaml
door:       POST /tokens/<sub>/<вид> у агента своего кластера; личность соединения — роль воркера одним из способов
            М10/11: сокет роли на коробке или сертификат роли (ADR-0075) в кластере; роль в теле не называется
body:       {request_id, ref, by?} — request_id 1–64 [A-Za-z0-9_-]; ref, by — непустые строки; больше TOKEN_BODY — 413
TOKEN_BODY: 4 KiB
answer:     200 {request_id, token, exp} — только этому соединению; иное — код и тело держателя как пришли
no_queue:   агент держит запрос, пока держатель не ответил (не дольше TOKEN_WAIT); не ответил — соединение рвётся,
            воркер просит заново; очереди ответов нет
TOKEN_WAIT: 10          # с
```

### Н1.3 Дверь держателя

```yaml
door:       POST /api/tokens/<член>/<sub>/<вид> у процесса domain; подпись агента (урок 3 Н1.4); через ретранслятор —
            байт в байт, той же подписью (урок 4)
body:       {request_id, role, ref, by?} — role — роль, которую агент удостоверил; формы как Н1.2
answer:     200 {sealed: <m1 урока 3 Н1.5>} — внутри текст JSON {request_id, token, exp}
agent:      открыть m1; request_id ≠ запрошенного или exp ≤ now — 502 {error: "invalid token reply"}; иначе отдать
```

### Н1.4 Утверждения

```yaml
payload:    {iss: <домен>, sub: <член-заявитель>, kind: <вид>, iat: now, exp: now + lifetime, jti: 16 hex,
             <ref_claim>: ref, <audience_claim>: [<член>…] по возрастанию, без повторов,
             scenario: <trigger_claim>: by, <acts_claim>: [<act>…] по JCS без повторов, <up_claim>?: centre}
signed:     ключом токенов держателя (current набора, урок 2 Н1.2), JCS header и payload (урок 2 Н1.6)
```

### Н1.5 Проверка у получателя

Получатель — воркер или дверь члена, которому адресован токен. Проверка — функция `token` урока 2 Н3 с `expect`:
`kind` — вид, которого он ждёт, `cluster` — свой кластер, `audience_claim` — из объявления вида. Токен, в аудитории
которого нет кластера-получателя, — `wrong_audience`; чужой вид — `wrong_kind`. Дальше получатель сверяет свои
утверждения (`ref_claim` — своя единица, у `scenario` — `acts`); их смысл — подсистемы.

---

## Н2 Двери

HTTP-контракт: [07-worker-tokens.api.openapi.yaml](07-worker-tokens.api.openapi.yaml).

| Дверь | Кто | Успех | Отказы |
|---|---|---|---|
| POST `/tokens/<sub>/<вид>` | агент, личность — роль | 200 `{request_id, token, exp}` | 401 личности роли нет; 404 нет маршрута; 400 тело; 413; код держателя — как пришёл; 502 ответ не открылся или не тот; 503 до держателя не дотянуться |
| POST `/api/tokens/<член>/<sub>/<вид>` | процесс `domain` | 200 `{sealed}` | урок 3 Н2 (подпись и член); 413; Н3 «выдать» — `{error: "refused", reason, detail}` |

---

## Н3 Проход

### выдать (процесс domain) — по порядку, первое правило даёт исход

```
1. член, ключ, подпись — урок 3 Н2                                       → 404 / 403 / 401
2. тело не по форме Н1.3                                                 → 400 bad_request
3. вид не объявлен спекой sub, или без области, или role ∉ grant          → 403 not_granted
4. by есть без scenario или нет у scenario                               → 400 by_misplaced
5. область:
   placement — запись <placement.sub>/<ref>:
     нечитаема                                                           → 403 assignment_unreadable
     нет: есть unit — к unit; иначе                                      → 403 no_assignment
     имя записи (cluster, origin, copies) не член, или член ≠ поле caller → 403 outside_scope
     аудитория: значения target_fields; centre/star_centre без centre     → 409 no_centre
   unit — владельцы ref (члены, чьи копии заявляют единицу с этим ref, урок 1):
     caller self: владелец — ровно этот член; caller poll_home: владелец один  → иначе 403 unit_not_unique
     caller poll_home: poll_home(владелец) ≠ член                         → 403 not_poll_home
     аудитория: poll_home(владелец), centre (без centre → 409 no_centre)
   scenario — by:
     владелец by один: член или член за этим ретранслятором (via[владелец] = член)  → иначе 403 trigger_not_reported
     общий документ doc (урок 11 Н1.2, проверенный record урока 10) → массив items; нет        → 403 no_shared_doc
     элементы: имя уникально, enabled не false, target = ref, trigger = by → acts; нет ни одного → 403 no_item
     дом: запись <placement>/<ref> — её cluster (в star — centre); иначе poll_home(единственного владельца ref)
                                                                          → нет → 403 no_home
     аудитория: подъём ретранслятора (заявитель — via владельца by) — [centre];
                заявитель за ретранслятором R: R = дом — [R], иначе [R] и up = centre;
                иначе — {дом} и centre, если он есть; у подъёма и за ретранслятором ≠ дом centre нужен → нет → 409 no_centre
6. аудитория пуста или с не членом                                       → 403 no_audience
7. утверждения Н1.4, подпись, m1 члену                                   → 200
```

Ничего не пишется: выдача — чтение записей, топологии, копий и документа. `detail` отказа называет причину словами, без
значений документа и токенов.

### проверить у получателя

```
token урока 2 с expect {kind: <вид>, cluster: <свой кластер>, audience_claim} → ok | refused (… | wrong_kind | wrong_audience)
```

**Гонки.** Назначение, топология или документ меняются после выдачи — токен живёт свой `lifetime`; отзыв — `domain/revoked`
урока 2. Два одинаковых запроса — два токена; память о выданных не нужна.

---

## Н4 Отказы

| Слово | Код | Когда |
|---|---|---|
| `bad_request` | 400 | тело не по форме |
| `by_misplaced` | 400 | `by` не у `scenario` или его нет у `scenario` |
| `not_granted` | 403 | вида нет, области нет, роль не в `grant` |
| `assignment_unreadable` | 403 | запись назначения нечитаема |
| `no_assignment` | 403 | записи нет, `unit` не объявлен |
| `outside_scope` | 403 | имя записи не член; член не в поле `caller` |
| `unit_not_unique` | 403 | у ref не ровно один владелец (или у `self` — не этот член) |
| `not_poll_home` | 403 | член — не ближайшая дверь владельца |
| `trigger_not_reported` | 403 | `by` заявляет не член (и не член за ним) |
| `no_shared_doc` | 403 | проверенного документа нет |
| `no_item` | 403 | подходящих включённых элементов нет |
| `no_home` | 403 | дом цели не определить |
| `no_audience` | 403 | аудитория пуста или с не членом |
| `no_centre` | 409 | нужен центр, его нет в топологии |
| `wrong_kind`, `wrong_audience` | у получателя | урок 2 Н3 `token` шаги 9–10 |

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/07/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/07/README.md)):
команда `issue` на входах `inputs/` и стенд урока 3 с местной дверью агента. Отказы объявления — случаи `m57_tokens_*`
корпуса урока 2.

```yaml
issue:      вход {domain, sub, kind, decl: <объявление вида> | null, role, member, body, members: [<член>…], holder,
                  placements: {"<sub>/<ref>": {cluster, origin, copies} | "garbled"}, topology: {centre?, star, via},
                  units: {<sub>: {<ref>: [<член>…]}}, shared: {<doc>: {<items>: [...]}} | null, now}
            вывод {result: ok, claims: <payload Н1.4 без jti>} | {result: refused, status, reason}
exit:       0 — вычислено; 2 — вход не по форме
```

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: `tally` члену из `origin` назначения — токен; принят кластером из `aud`, отвергнут кластером вне `aud` (`wrong_audience`) и с чужим видом (`wrong_kind`) | Н1.2–Н1.5, урок 2 |
| 02 | стенд: роль не в `grant`, член не `origin`, назначения нет — 403 со словом | Н3 |
| 03 | `issue`: placement, unit (`self`, `poll_home`), переход placement → unit, scenario (прямо, за ретранслятором, подъём, дом по назначению), все слова отказов | Н3 |

---

## Решает реализация

1. **команду `issue`** — шаблон с `{input}`; **как раннер стенда обращается к местной двери агента** с личностью роли
   (сокет роли или комплект сертификата роли) — для двери `token` словаря М11/01;
2. **как воркер держит токен** в памяти и когда просит новый (не позже `exp`).

---

## Чеклист готовности

- [ ] **М11/7-01** объявление вида Н1.1 и отказы загрузки — случаи `m57_tokens_*` урока 2
- [ ] **М11/7-02** местная дверь: роль из личности соединения, тело, 4 KiB, без очереди — сц. 01, 02; ожидание и обрыв — чтением
- [ ] **М11/7-03** дверь держателя и ответ `m1`, проверка `request_id` и `exp` агентом — сц. 01
- [ ] **М11/7-04** выдача Н3 по порядку и слова отказов — сц. 02, 03
- [ ] **М11/7-05** утверждения Н1.4: `sub` — член, аудитория по возрастанию, `acts` по JCS, `up` — сц. 03
- [ ] **М11/7-06** у получателя `wrong_audience`/`wrong_kind` — сц. 01; урок 2 сц. 12
- [ ] **М11/7-07** токен только в памяти воркера, не в журнале — чтением
- [ ] **М11/7-08** через ретранслятор — байт в байт — чтением (стенд урока 4 его дорогу проверяет)

## Соответствие прежним урокам

Прежнего урока о токенах воркеров в М12A нет (токены книг вёл `domainpart`, урок 4 М12A — токены людей — урок 9).
Урок нормирует ADR-0074 доп. (5), C4, C6, C6b и решение «Архитектора» по вопросам М11/7. Исторические исходники сохранены в Git.

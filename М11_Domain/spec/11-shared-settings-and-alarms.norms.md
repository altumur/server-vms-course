# М11/11 — Общие настройки и тревоги членов: нормы

Канон урока. [Лекция](../11-shared-settings-and-alarms.md), [HTTP-контракт](11-shared-settings-and-alarms.api.openapi.yaml),
[инструкция](11-shared-settings-and-alarms.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md).

## Н0 Словарь слов

Нормативные слова — по [общему канону Н0](../../М10_Platform/spec/01-storage.norms.md#н0-словарь-слов). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

Общее уроков 1–10 Н1 действует. Домен не знает ни одного поля подсистемы (ADR-0010): что общее, объявляет спека, а
значение домена разрешается **при чтении**, не записью в строки. Тревоги членов домен собирает из их отчётов: к члену он
соединений не открывает. Решение «Архитектора» по вопросам М11/11; C6 «точный документ».

### Н1.1 Объявление `domain.shared`

```yaml
domain.shared:   [<элемент>…]            # раздел спеки (М10/2 Н1.2а, добавлено М11/11)
  element:       <имя поля единицы> | {name, type: json, schema}     # у документа ровно эти три ключа
  field:         поле unit.fields, не секрет (М10/7 Н1.1); наследует (inherit) или это display.tree.group_by
  document:      name — ^[a-z][a-z0-9_-]*$, не имя поля единицы; schema — JSON Schema (М10/3 schemes), по ней проверяется значение
refusals:        refused:value с путём domain.shared[<i>] (М10/2 Н4; случаи m61_* корпуса М10/2), тексты:
  - «is not {name, type: json, schema} — a document the domain holds is JSON, and what it may be is its schema»
  - «is not a name, or is a secret — the shared document is signed, not sealed»
  - «is not a field of the unit»
  - «is a field of the unit — a document the domain holds whole is no unit's: name it apart»
  - «neither inherits nor is the field the page groups by (display.tree.group_by) — a domain value it would have nowhere to go»
  - «names one thing twice»
merge:           unit.fields.<f>.merge (М10/2): override | union; только с inherit; union — только у type list
                 (иначе refused:value «merge is override or union (a list's) — said of a field that inherits»)
```

### Н1.2 Общий документ

```yaml
document:        объект держателя domain/shared-docs/rev-<rev> — JCS {domain, term, rev, at, by, shared, issuer, kid, sig}
  shared:        {<sub>: {<имя>: <значение>}} — только объявленное Н1.1; подсистемы и имена по возрастанию (JCS)
  term, rev:     срок держателя (урок 10) и номер правки; порядок — (term, rev), term старше
  by:            имя, доказанное сторожевой; после переноса — "domain"
  signature:     выпускающий ключ, как запись срока (урок 10 Н1.1, проверка — record); неподписанный не принимается никогда
pointer:         domain/shared {doc: JCS {term, rev, sha256, object}} у держателя; sha256 — hex sha256 текста объекта
write:           сначала объект, затем указатель по CAS (две правки одновременно — одна получает 409); держатель хранит
                 последние 5 объектов
after_move:      новый держатель (урок 10 Н1.8) переподписывает то же содержимое как rev + 1, by "domain" — у него другой
                 выпускающий; при плановой передаче выпускающий тот же, документ не меняется
readers:         процесс domain, консоль домена, воркер подсистемы на домене (роль <sub>domain) — указатель domain/shared
                 (точное имя) и объекты domain/shared-docs/rev-* (семья domain/* двери объектов М10/8); консоль кластера — строка domain/shared (точное имя: у держателя
                 указатель, у члена строка копии, Н1.4; М10/6 Н1.4 console, добавлено М11/11); проекций по подсистемам нет (C6)
```

### Н1.3 Правка

```yaml
door:            PUT /domain/shared {base_rev, shared: {<sub>: {<имя>: <значение> | null}}} у консоли домена (admin, урок 9)
                 → процесс domain тем же путём (ADR-0032); тело ≤ 1 МиБ (иначе 413 {error: "refused"})
order:           1. заморозка, смещение — урок 10 (503 frozen, 409 deposed)
                 2. тело не {base_rev: целое ≥ 0, shared: объект} — 400 {error: "refused", detail: "the edit is {base_rev:
                    <the revision it was made against>, shared: {<sub>: {<field>: value or null}}}"}
                 3. base_rev ≠ rev указателя (0 — документа нет) — 409 {error: "refused", detail: "the shared settings are at
                    rev N; the edit was made against rev M — look again"}
                 4. содержание — все отказы одним 400 через «; »: «shared settings for '<sub>': no subsystem on the domain
                    shares a field by that name»; «'<имя>' is not in its domain.shared [<имена domain.shared спеки через «, », по возрастанию>]»; тип поля — та же проверка
                    формы, что у двери единиц (М10/3 Н3 шаг 4), на одном этом поле, слово отказа — её; значение документа
                    против его schema (слова схемы)
                 5. новый документ: прежний shared, поверх — значения правки; null — снять имя; пустая подсистема —
                    снять; rev + 1, term — свой, at, by
                 6. записать (Н1.2 write); CAS не прошёл — 409 «the shared settings changed while this edit was made — look again»
answer:          200 {term, rev, by}; журнал domain.shared.edited {term, rev, by}
```

### Н1.4 Доставка члену

```yaml
carry:           ответ держателя агенту (урок 3 Н1.5) несёт shared: {pointer: {term, rev, sha256}, doc?: <текст>} — doc,
                 только когда domain/shared из копии члена ≠ указателю (урок 3 «прочитать копию»)
member:          агент по порядку (Н3 «взять документ»); затем объект domain/shared = текст, затем строка
                 domain/shared {doc: JCS {term, rev, sha256}}; отказ — строка domain/shared-refused {doc: JCS {term, rev,
                 reason, at}}; прежний документ остаётся
in_report:       строки domain/shared и domain/shared-refused — объекты отчёта (урок 3 Н1.2 member_objects, добавлено М11/11)
holder_self:     у кластера держателя строка domain/shared — указатель (Н1.2), а документ — объект domain/shared-docs/rev-<rev>: агент
                 держателя документа не берёт, консоль держателя читает указатель (Н1.5)
```

### Н1.5 Значение при чтении

```yaml
resolve:         функция Н3 — значение поля для единицы: единица → домен → inherit спеки
door:            GET /domain/shared/<sub>[?unit=<id>] у консоли кластера (своя, не пересылается; view) →
                 200 {sub, term, rev, fields: {<имя>: <запись>}} — по каждому элементу domain.shared этой спеки
  record:        поле — {value, from, inherit, merge?} (merge — только union); group_by — {groups, from}; документ — {value, from}
  term, rev:     документа этого кластера: у члена — объект domain/shared (копия, взятая Н3), у держателя — объект, который
                 называет указатель; документа нет — null, значения — без домена
refusals:        подсистема без domain.shared — 404 {error: "no such shared settings", detail: "'<sub>' shares no field with the
                 domain"}; ?unit= не id этой спеки — 400 {error: "refused", detail: «a unit of <другая> is resolved by its own console»}; единицы нет
                 — 404 {error: "no such unit"}; документ не проходит record — значения без домена, journal domain.shared.refused
```

### Н1.6 Доставлено скольким

```yaml
domain/view.shared:  {term, rev, holding, behind, refused, silent, sentence}       # урок 1 Н1.4, добавлено М11/11
  holding:     [<член>…] — копия члена ≥ (term, rev) указателя; держатель включён
  behind:      {<член>: {term, rev}} — держит старее
  refused:     {<член>: <reason>} — domain/shared-refused члена с (term, rev) указателя
  silent:      [<член>…] — член не ok по виду (урок 1); раньше прочих правил
  sentence:    «rev R on H of T members[; not taken yet: …][; not answering: …][; refused by: <член> (<reason>), …]»
door:          GET /domain/shared у консоли домена (view) → 200 {doc, delivery, declared}
  doc:         документ как подписан (объект) | null
  delivery:    view.shared
  declared:    {<sub>: [{name, type, schema?}]} — элементы domain.shared спек каталога, по name; schema — у документа
               (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10a, добавлено М11/11)
```

### Н1.7 Страница тревог члена

```yaml
page:          объект отчёта domain/alarms (урок 3 Н1.2 member_objects, добавлено М11/11):
               {from, to, events, truncated}
  events:      строки индекса М10/8 Н1.3 класса alarm всех спек каталога: GET /events?class=alarm&from=<to − ALARM_WINDOW>
               &to=<now>&limit=ALARM_PAGE&keep=newest у своей консоли (М10/8 merge) — {id, subsystem, unit, of, t, kind, …}
  from, to:    окно страницы по стенным часам члена; to — момент сборки
  truncated:   truncated ответа индекса > 0
ALARM_WINDOW:  86400       # с
ALARM_PAGE:    100
urgent:        раз в секунду агент читает только фронт — GET /events?class=alarm&limit=1&keep=newest своей консоли; t
               строки > to прошлой страницы — собрать страницу и отправить отчёт сейчас, вне очередного прохода, но не
               чаще URGENT_GAP после прошлого срочного; цена — одно чтение строки индекса в секунду на член, не больше
               (урок 12 Н1.9: сотни членов)
rebuild:       страница собирается при старте агента и когда фронт новее to; иначе отчёт несёт прежнюю страницу — спокойный
               член поколений не порождает (урок 12 Н1.2)
URGENT_GAP:    1           # с
identity:      агент ходит к /events своей консоли подписью агента (урок 3 Н1.4; М10/9 Н1.3 identity шаг 2, добавлено М11/11)
```

### Н1.8 Список тревог у держателя

```yaml
door:          GET /domain/alarms?since=&until= у консоли домена (view); умолчание — сутки до now; не конечные числа или
               since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}
answer:        200 {since, until, events, members, complete, sentence} — функция alarms (Н3) на странице последнего отчёта
               каждого члена списка (держатель включён), истории (Н1.9) и свидетелях
member_state:  ok | silent | not_reporting | never | unreadable
  silent:      последний отчёт старше LOST_AFTER (вид урока 1, 45 с); silent_since = последний отчёт + LOST_AFTER
  not_reporting: silent, а свидетель слышал единицу члена позже последнего отчёта
  never:       отчёта не было ни разу
  unreadable:  страница не по форме Н1.7 (у функции alarms — и вход "garbled")
silence_line:  молчащий член — строка тревоги {t: silent_since, kind: silent | not_reporting, class: alarm, member,
               subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?} — всегда, пока молчит
witness:       domain.witness {report, member_field} (М10/2): объекты <sub>/<report>/<имя> = {ts, cluster, units: {<член>:
               секунды с последнего раза}} у кластеров и в отчётах; member_field — fixed поле единицы, несущее имя члена
               (иначе refused:value с путём domain.witness.member_field, текст «'<поле>' is no fixed field of the unit: a
               witness names a member by a field that does not change»); alive_at = ts − units[член], alive_via = "<cluster>/<имя>"; свидетелей несколько —
               наибольший alive_at среди тех, что позже last_report
clock:         время строки страницы на часах домена: t + (received_at − sent_at) последнего принятого отчёта, который
               несёт эту страницу (поля последнего запроса метки, урок 3 Н1.3); не page.to: прежняя страница в новом отчёте
               старые тревоги вперёд не сдвигает (решение «Архитектора» по R41-16 прогона 41); t_src — t как пришло
events_order:  по t убывая, затем member, id; строки истории — from_history: true
```

### Н1.9 История тревог

```yaml
history:       объект держателя domain/alarm-history/<член> {events, cut_before} — скользящая неделя, не больше
               HISTORY_LINES строк, самые новые; cut_before — с какого момента член держится целиком
  events:      строки страницы, как приняты: t — на часах домена (Н1.8 clock), t_src — как пришло
HISTORY_DAYS:  7
HISTORY_LINES: 2000
writer:        только проход держателя (процесс domain, ADR-0032): после приёма отчёта дописать строки его страницы,
               которых нет; список (Н1.8) историю только читает
same_line:     (t_src, kind, subsystem, unit) — по часам члена: поправка часов меняется от отчёта к отчёту
in_copy:       история едет с резервной копией держателя (урок 10 Н1.5 objects, добавлено М11/11)
```

---

## Н2 Двери

HTTP-контракт: [11-shared-settings-and-alarms.api.openapi.yaml](11-shared-settings-and-alarms.api.openapi.yaml). Тело отказа —
`{error, detail}`. Двери `/domain/shared` и `/domain/alarms` консоли домена — строки таблицы пересылки урока 8 (добавлено
М11/11); `/domain/shared/<sub>` — своя у консоли кластера.

| Дверь | Кто | Успех | Отказы |
|---|---|---|---|
| GET `/domain/shared` | консоль домена | Н1.6 | 401/403 |
| PUT `/domain/shared` | консоль домена → процесс `domain` | `{term, rev, by}` | Н1.3 |
| GET `/domain/shared/<sub>[?unit=]` | консоль кластера | Н1.5 | Н1.5 |
| GET `/domain/alarms?since=&until=` | консоль домена | Н1.8 | 400; 401/403 |

---

## Н3 Проход

### взять документ (агент члена, после записи срока урока 10)

```
1. shared ответа нет, или (term, rev) указателя ≤ своей строки domain/shared   → ничего (up to date | holding newer)
2. doc нет                                                                       → ничего: придёт следующим ответом
3. sha256 текста ≠ pointer.sha256                                                → refused «the object does not match the pointer's checksum»
4. record (урок 10 Н3) по своему набору не ok                                    → refused «<слово record>»
5. (term, rev) документа ≠ указателю                                             → refused «the object is term T rev R, the pointer says otherwise»
6. записать объект, затем строку (Н1.4)
```

### resolve(field, unit, domain)

```
вход:   field {name, type, inherit?, merge?, group_by?, document?}; unit — значение строки единицы | отсутствует;
        domain — {term, rev, value} значения в документе | null
label:  "domain term T rev R"
1. document              → {value: domain ? domain.value : null, from: domain ? label : "none"}
2. group_by              → {groups: domain ? domain.value : [], from: domain ? label : "none"}   # groups — в порядке domain.value
3. unit есть, merge union, domain есть → {value: sorted(unit ∪ domain.value), from: "unit + " + label}
4. unit есть             → {value: unit, from: "unit"}
5. domain есть           → {value: domain.value, from: label}
6.                       → {value: field.inherit, from: "spec"}
```

### alarms(input)

```
вход:   {now, since, until, lost_after, members: {<член>: {last_report: <часы домена> | null, received_at, sent_at, page: <Н1.7> |
         "garbled" | null, history: <Н1.9> | null}}, witnesses: [{sub, name, ts, cluster, units}]}
1. каждый член:
   last_report нет и page нет                         → never
   last_report нет, а page есть                       → вход не по форме (код 2): страница приходит только с отчётом
   page = "garbled" или не по форме Н1.7              → unreadable
   now − last_report > lost_after                     → silent; свидетель с ts − units[член] > last_report — not_reporting
   иначе                                              → ok
   page = null при last_report — страницы нет: строк страницы нет, не unreadable
2. строки: страница (часы Н1.8 clock) ∪ история (from_history, t как хранится) без повторов по same_line — есть в обеих,
   берётся строка страницы; строка молчания — Н1.8 silence_line; окно [since, until] — для всех строк, и для строки
   молчания
3. members: {<член>: {state, truncated?, known_until?, silent_since?, alive_at?, alive_via?, history_cut_before?}};
   truncated: true — у читаемой страницы с truncated; known_until — last_report у silent/not_reporting;
   history_cut_before — у истории с cut_before > since
4. complete = все ok; sentence — «every member answered» или фразы через «; », по членам (байты UTF-8), у члена — в
   порядке списка ниже:
   «<m> silent since <HH:MM> — its alarms from its last report, known up to <HH:MM> UTC; none known since»
   «… — but <alive_via> heard of it at <HH:MM>: alive, and not reporting to the domain»
   «<m> has never reported to the domain»; «<m>'s page of alarms does not read»
   «<m> had more alarms than one page holds; showing its newest»
   «<m> had an alarm storm: the domain keeps only its newest alarms, and what came before <HH:MM> UTC is not known in full»
   (время — UTC часов домена)
```

**Гонки.** Две правки общего документа — CAS указателя, вторая — 409. Член без связи держит свою ревизию и значения
домена по ней; вернувшись, берёт новую. Шторм тревог — страница с `truncated`, отчёт не чаще `URGENT_GAP`. Держатель
перенесён — новый переподписывает документ (`rev + 1`), члены берут его как новый.

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `refused` | 400, 409, 413 | правка (Н1.3), тело больше 1 МиБ — 413; окно `/domain/alarms`; `?unit=` — id другой спеки (Н1.5) |
| `standby` | 503 | процесс `domain` — ждущий (урок 12 Н1.7) |
| `no such shared settings` | 404 | подсистема без `domain.shared` |
| `no such unit` | 404 | `?unit=` нет такой единицы |
| `frozen`, `deposed` | 503, 409 | урок 10 |

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/11/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md)):
стенд урока 3 (каталог `testsub`: поля `step`, `marks`, документ `rounds`) и команды `resolve`, `alarms` на входах
`inputs/`. Отказы `domain.shared`, `merge` и `domain.witness` — случаи `m61_*` корпуса М10/2.

```yaml
resolve:   вход {field, unit?, domain}; вывод {value, from} | {groups, from}
alarms:    вход — Н3 alarms; вывод {events, members, complete, sentence}
exit:      0 — вычислено; 2 — вход не по форме (у resolve — и merge union при значении не списке; ожидания кода 2 в словаре
           нет — чтением)
```

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: правка — 200; старая `base_rev` — 409; поле не общее, тип, схема — один 400; `m1` берёт документ, `GET /domain/shared/testsub?unit=` с `from`, `union` у `marks`; доставка | Н1.2–Н1.6 |
| 02 | стенд: агент `m2` выключен — в доставке `silent`, строка тревоги `silent` в `/domain/alarms`; вернулся — взял документ | Н1.6, Н1.8 |
| 03 | `resolve`: своё, домена, объединение, спеки, документ, группы, домена нет | Н3 resolve |
| 04 | `alarms`: все ответили; шторм `truncated`; молчит — последний отчёт; свидетель — `not_reporting`; ни разу; страница не читается; история без повторов и `history_cut_before`; окно | Н3 alarms |
| 05 | неподписанный документ, положенный мимо правки: член не берёт — `domain/shared-refused` `not_a_record` (мутационная проверка 2026-10-18) | Н1.2 `signature`, Н3 «взять документ» |
| 06 | указатель с чужой суммой: член не берёт документ — `domain/shared-refused` «does not match the pointer» (мутационная проверка, класс сумм) | Н3 «взять документ» шаг 3 |

---

## Решает реализация

1. **команды `resolve` и `alarms`** — шаблоны с `{input}`;
2. **как агент собирает страницу** — запрос к индексу своей консоли или к ресурсам напрямую, лишь бы форма и фронт Н1.7
   сохранялись.

---

## Чеклист готовности

- [ ] **М11/11-01** объявление Н1.1, `merge` и `domain.witness` — случаи `m61_*` корпуса М10/2
- [ ] **М11/11-02** документ Н1.2: форма, подпись выпускающим, указатель, пять объектов, `rev + 1` после переноса — сц. 01; переподпись — чтением
- [ ] **М11/11-03** правка Н1.3 по порядку, все отказы одним 400 — сц. 01
- [ ] **М11/11-04** доставка Н1.4: `doc` только при расхождении, проверка агента, никогда назад, отказ — сц. 01, 02; подделка — урок 10 `record`
- [ ] **М11/11-05** значение при чтении Н1.5 — сц. 01, 03; `?unit=` другой спеки — чтением (каталог стенда урока 11 — одна спека)
- [ ] **М11/11-06** доставлено скольким Н1.6, `declared` со схемой — сц. 01, 02
- [ ] **М11/11-07** страница тревог Н1.7, фронт раз в секунду, срочный отчёт — чтением (стенд тревог не поднимает)
- [ ] **М11/11-08** список Н1.8: состояния, строка молчания, свидетель — сц. 02, 04
- [ ] **М11/11-09** история Н1.9: один писатель, предел, без повторов, в резервной копии урока 10 — сц. 04; писатель — чтением

## Соответствие прежним урокам

Нормирует то, что рассказывали `М12A_Domain/12-shared-settings-without-a-database.md` (шаги 1–8; шаг 9 — сценарии VMS
— М12) и `М12A_Domain/13-alarms-from-every-member.md` (шаги 1–7). ADR-0010, ADR-0032, решения C6 «точный документ»,
C6 «testsub2». Исторические исходники сохранены в Git.

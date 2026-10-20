# М11/11 — Общие настройки и тревоги членов: нормы

Канон урока. [Лекция](../11-shared-settings-and-alarms.md), [HTTP-контракт](11-shared-settings-and-alarms.api.openapi.yaml),
[инструкция](11-shared-settings-and-alarms.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md).

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

**Время.** Поля времени строк и объектов урока — время по [канону Н0](../../Platform/01-store/spec/01.1-store.norms.md#время-в-строке): объект страницы `domain/alarms` — `from`, `to`; объект истории `domain/alarm-history/<член>` — `events[].t`,
`cut_before` (писатель — не больше трёх знаков дроби; добавлено сверкой М11, A22).

**Данные** ([каталог](../../Platform/common/data/catalog.tsv)):
- владеет: `domain/shared`, `domain/shared-docs/rev-<rev>`, `domain/shared-refused`, `domain/alarms`, `domain/alarm-history/<член>`, `<sub>/<spec:domain.witness.report>/<имя>`;
- читает: `domain/holder`, `domain/members/<член>/reports/<rev>`, `domain/members/<член>/reported`.

Общее уроков 1–10 Н1 действует. Домен не знает ни одного поля подсистемы (ADR-0010): что общее, объявляет спека, а
значение домена разрешается **при чтении**, не записью в строки. Тревоги членов домен собирает из их отчётов: к члену он
соединений не открывает. Решение «Архитектора» по вопросам М11/11; C6 «точный документ».

### Н1.1 Объявление `domain.shared`

Перенесено в [P/02.1 Н1.2б](../../Platform/02-installer/spec/02.1-installer.norms.md) (стадия B; глава позднего слоя, вводит урок 8).

### Н1.2 Общий документ

```yaml
document:        объект держателя domain/shared-docs/rev-<rev> — JCS {domain, term, rev, at, by, shared, issuer, kid, sig}
  shared:        {<sub>: {<имя>: <значение>}} — только объявленное P/02.1 Н1.2б; подсистемы и имена по возрастанию (JCS)
  term, rev:     срок держателя (урок 10) и номер правки; порядок — (term, rev), term старше
  by:            имя, доказанное сторожевой; после переноса — "domain"
  signature:     выпускающий ключ, как запись срока (урок 10 Н1.1, проверка — record); неподписанный не принимается никогда
pointer:         domain/shared {doc: JCS {term, rev, sha256, object}} у держателя; sha256 — hex sha256 текста объекта
write:           сначала объект, затем указатель по CAS (две правки одновременно — одна получает 409); держатель хранит
                 последние 5 объектов; объект ревизии пишется, только если его нет или его байты те же — иначе правке 409
                 «the shared settings changed while this edit was made — look again» и объект не трогается: проигравшая
                 правка не перезаписывает объект выигравшей (добавлено сверкой М11, A1)
after_move:      новый держатель (урок 10 Н1.8) переподписывает то же содержимое как rev + 1, by "domain" — у него другой
                 выпускающий; при плановой передаче выпускающий тот же, документ не меняется
readers:         процесс domain, консоль домена, воркер подсистемы на домене (роль <sub>domain) — указатель domain/shared
                 (точное имя) и объекты domain/shared-docs/rev-* (семья domain/* двери объектов P/05); консоль кластера — строка domain/shared (точное имя: у держателя
                 указатель, у члена строка копии, Н1.4; P/02.5 Н1.4 console, добавлено М11/11); проекций по подсистемам нет (C6)
```

### Н1.3 Правка

```yaml
door:            PUT /domain/shared {base_rev, shared: {<sub>: {<имя>: <значение> | null}}} у консоли домена (admin, урок 9)
                 → процесс domain тем же путём (ADR-0032); тело ≤ 1 МиБ (иначе 413 {error: "refused"})
order:           1. заморозка, смещение — урок 10 (503 frozen, 409 deposed)
                 2. тело не {base_rev: целое ≥ 0, shared: объект, каждое shared.<sub> — объект} — 400 (shared.<sub> не
                    объект — тоже здесь, до base_rev; добавлено сверкой М11, A9) {error: "refused", detail: "the edit is {base_rev:
                    <the revision it was made against>, shared: {<sub>: {<field>: value or null}}}"}
                 3. base_rev ≠ rev указателя (0 — документа нет) — 409 {error: "refused", detail: "the shared settings are at
                    rev N; the edit was made against rev M — look again"}
                 4. содержание — все отказы одним 400 через «; »: «shared settings for '<sub>': no subsystem on the domain
                    shares a field by that name»; «'<имя>' is not in its domain.shared [<имена domain.shared спеки через «, », по возрастанию>]»; тип поля — та же проверка
                    формы, что у двери единиц (P/06.1 Н3 «создать» шаг 4), на одном этом поле, слово отказа — её; значение документа
                    против его schema (слова схемы); значение, которое консоль запечатала бы (P/06.2 Н3) (имя *_secret на любой глубине,
                    находка пароля в адресе по P/06.2 Н1.1а), — «'<имя>': the shared document is signed, not sealed» (сверка М11, A6)
                 5. новый документ: прежний shared, поверх — значения правки; null — снять имя; пустая подсистема —
                    снять; rev + 1, term — свой, at, by; прежний документ (объект, который называет указатель) не читается
                    или не с его sha256 — 503 {error: "refused", detail: "the shared document at rev N does not read: nothing
                    is written"}, ничего не пишется: правка поверх пустого потеряла бы прежние значения (сверка М11, A7)
                 6. записать (Н1.2 write); CAS не прошёл — 409 «the shared settings changed while this edit was made — look again»
answer:          200 {term, rev, by}; журнал domain.shared.edited {term, rev, by}
```

### Н1.4 Доставка члену

```yaml
carry:           ответ держателя агенту (урок 3 Н1.5) несёт shared: {pointer: {term, rev, sha256}, doc?: <текст>} — doc,
                 только когда domain/shared из копии члена ≠ указателю (урок 3 «прочитать копию»)
member:          агент по порядку (Н3 «взять документ»); затем объект domain/shared = текст, затем строка
                 domain/shared {doc: JCS {term, rev, sha256}}; отказ — строка domain/shared-refused {doc: JCS {term, rev,
                 reason, at}}; прежний документ остаётся; взятый документ снимает строку domain/shared-refused с парой не
                 новее своей (добавлено сверкой М11, A4)
in_report:       строки domain/shared и domain/shared-refused — объекты отчёта (урок 3 Н1.2 member_objects, добавлено М11/11)
                 одной формой: значение объекта — разобранный doc строки, {term, rev, sha256} и {term, rev, reason, at},
                 term и rev — целые JSON (как domain/backup-taken урока 10; решение «Архитектора» по сверке М11, A3);
                 у кластера держателя строка domain/shared — указатель держателя, и агент несёт его doc целиком:
                 {term, rev, sha256, object} (добавлено пилотом схем семей данных, Д1)
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
                 domain"}; ?unit= пустой или повторён — 400 {error: "refused", detail: "a unit id is required"} (как урок 1
                 Н4 ?cluster=; добавлено сверкой М11, A11); единицы нет — в том числе единица другой спеки (её разрешает своя
                 консоль; решение «Архитектора» по сверке М11) — или id не по грамматике P/06.1 Н1.3 (в том числе `..` после
                 декодирования) — 404 {error: "no such unit"}; документ не
                 проходит record — значения без домена, journal domain.shared.refused
```

### Н1.6 Доставлено скольким

```yaml
domain/view.shared:  {term, rev, holding, behind, refused, silent, sentence}       # урок 1 Н1.4, добавлено М11/11
  holding:     [<член>…] — копия члена ≥ (term, rev) указателя; держатель включён
  behind:      {<член>: {term, rev}} — держит старее; член без копии — {term: 0, rev: 0}, не null (добавлено пилотом схем семей данных, Д2)
  refused:     {<член>: <reason>} — domain/shared-refused члена с (term, rev) указателя
  silent:      [<член>…] — член не ok по виду (урок 1); раньше прочих правил
  sentence:    «rev R on H of T members[; not taken yet: …][; not answering: …][; refused by: <член> (<reason>), …]»
  before:      до первого документа (указателя нет): term 0, rev 0, holding [], behind {}, refused {}, silent — по виду,
               sentence «rev 0 on 0 of T members» с теми же хвостами (решение «Архитектора» по сверке М11, A5)
door:          GET /domain/shared у консоли домена (view) → 200 {doc, delivery, declared}
  doc:         документ как подписан (объект) | null
  delivery:    view.shared
  declared:    {<sub>: [{name, type, schema?}]} — элементы domain.shared спек каталога, по name; schema — у документа
               (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10a, добавлено М11/11; поздний слой P/07 Н1.6)
```

### Н1.7 Страница тревог члена

```yaml
page:          объект отчёта domain/alarms (урок 3 Н1.2 member_objects, добавлено М11/11):
               {from, to, events, truncated}
  events:      строки индекса P/05 Н1.3 класса alarm всех спек каталога: GET /events?class=alarm&from=<to − ALARM_WINDOW>
               &to=<now>&limit=ALARM_PAGE&keep=newest у своей консоли (P/06.4 Н1.3 merge) — {id, subsystem, unit, of, t, kind, …}
  event:       строка страницы — форма строки индекса P/05 Н1.3: id — непустая строка (обязателен), class = alarm, kind —
               непустая строка, unit — строка, t — число; строка не по этой форме (в том числе без id) — страница не по
               форме: у держателя член unreadable (Н3 alarms шаг 1; решение «Архитектора» по сверке М11, H14, A15)
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
identity:      агент ходит к /events своей консоли подписью агента (урок 3 Н1.4; P/06.3 Н1.3 identity шаг 2, добавлено М11/11)
```

### Н1.8 Список тревог у держателя

```yaml
door:          GET /domain/alarms?since=&until= у консоли домена (view); умолчание — сутки до now; не конечные числа или
               since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}; число — по
               грамматике числа JSON целиком (без пробелов, «+», «_»), параметр не повторён (добавлено сверкой М11, A12)
answer:        200 {since, until, events, members, complete, sentence} — функция alarms (Н3) на странице последнего отчёта
               каждого члена списка (держатель включён), истории (Н1.9) и свидетелях
member_state:  ok | silent | not_reporting | never | unreadable
  silent:      последний отчёт старше LOST_AFTER (вид урока 1, 45 с); silent_since = последний отчёт + LOST_AFTER
  not_reporting: silent, а свидетель слышал единицу члена позже последнего отчёта
  never:       отчёта не было ни разу
  unreadable:  страница не по форме Н1.7 (у функции alarms — и вход "garbled")
silence_line:  молчащий член — строка тревоги {t: silent_since, kind: silent | not_reporting, class: alarm, member,
               subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?} — всегда, пока молчит
witness:       domain.witness {report, member_field} (P/02.1 Н1.2б): объекты <sub>/<report>/<имя> = {ts, cluster, units: {<член>:
               секунды с последнего раза}} у кластеров и в отчётах; семья — ключи <sub>/<report>/<имя> (имя после «/»), агент
               несёт каждый объект семьи как объект отчёта (урок 3 Н1.2 member_objects), объект <sub>/<report> без имени —
               не свидетель (добавлено сверкой М11, A2); member_field — fixed поле единицы, несущее имя члена
               (отказ загрузки — P/02.1 Н1.2б); alive_at = ts − units[член], alive_via = "<cluster>/<имя>"; свидетелей несколько —
               наибольший alive_at среди тех, что позже last_report; при равном — меньший alive_via в байтах UTF-8
               (добавлено сверкой М11, A17)
clock:         время строки страницы на часах домена: t + (received_at − sent_at) последнего принятого отчёта, который
               несёт эту страницу (поля последнего запроса метки, урок 3 Н1.3); не page.to: прежняя страница в новом отчёте
               старые тревоги вперёд не сдвигает (решение «Архитектора» по R41-16 прогона 41); t_src — t как пришло
events_order:  по t убывая, затем member, id; строки истории — from_history: true
```

### Н1.9 История тревог

```yaml
history:       объект держателя domain/alarm-history/<член> {events, cut_before} — скользящая неделя, не больше
               HISTORY_LINES строк, самые новые; cut_before — с какого момента член держится целиком: число (часы домена),
               при создании истории — 0, не null (добавлено сверкой М11, A13)
cut:           cut_before двигается только при фактическом снятии строк: сняты строки с t < now − HISTORY_DAYS × 86400 —
               cut_before = max(cut_before, now − HISTORY_DAYS × 86400); сняты самые старые сверх HISTORY_LINES —
               cut_before = max(cut_before, t самой новой снятой); ничего не снято — объект истории не меняется, и тихий
               член не двигает rev резервной копии (урок 10 Н1.5 rev); начальный 0; cut_before не убывает (добавлено
               сверкой М11, A14; решение «Архитектора» по cammeta-go М11-03 № 11: прежнее «на каждом проходе» меняло
               содержимое копии само)
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
4. record (урок 10 Н3) по своему набору с видом «общий документ» (P/02.1 Н1.2б document; добавлено описью семей) не ok
                                                                                 → refused «<слово record>»
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

Фильтр — у двери, форма — у функции: дверь тревог собирает вход из хранилища и битого свидетеля (без ts и т. п.)
отбрасывает со счётчиком до вызова — устойчивость; вектор alarms получает уже собранный вход, и свидетель не по форме в
нём — вход не по форме, код 2 (H14). Одно другому не противоречит (добавлено сверкой М11, cammeta-python М11-11 № 20).

```
вход:   {now, since, until, lost_after, members: {<член>: {last_report: <часы домена> | null, received_at, sent_at, page: <Н1.7> |
         "garbled" | null, history: <Н1.9> | null}}, witnesses: [{sub, name, ts, cluster, units}]}
1. каждый член:
   last_report нет и page нет                         → never
   last_report нет, а page есть                       → вход не по форме (код 2): страница приходит только с отчётом
   page = "garbled" или не по форме Н1.7              → unreadable; не по форме — и строка без id, class ≠ alarm, kind
                                                        пустой, unit не строка, from > to (добавлено сверкой М11, A15)
   now − last_report > lost_after                     → silent; свидетель с ts − units[член] > last_report — not_reporting
   иначе                                              → ok
   page = null при last_report — страницы нет: строк страницы нет, не unreadable
2. строки: страница (часы Н1.8 clock) ∪ история (from_history, t как хранится) без повторов по same_line — есть в обеих,
   берётся строка страницы; повтор внутри одной страницы — первая по порядку страницы (сверка М11, A16); строка молчания — Н1.8 silence_line; окно [since, until] — для всех строк, и для строки
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
перенесён — новый переподписывает документ (`rev + 1`), члены берут его как новый. Обрыв между объектом и указателем
(Н1.2 write): объект выше указателя ничей, указатель прежний; следующая правка пишет поверх.

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `refused` | 400, 409, 413, 503 | правка (Н1.3), тело больше 1 МиБ — 413, прежний документ не читается — 503 (сверка М11, A7); окно `/domain/alarms`; `?unit=` пустой или повторён (Н1.5) |
| `standby` | 503 | процесс `domain` — ждущий (урок 12 Н1.7) |
| `no such shared settings` | 404 | подсистема без `domain.shared` |
| `no such unit` | 404 | `?unit=` нет такой единицы, в том числе единица другой спеки (решение «Архитектора» по сверке М11) |
| `frozen`, `deposed` | 503, 409 | урок 10 |

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/11/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md)):
стенд урока 3 (каталог `testsub`: поля `step`, `marks`, документ `rounds`) и команды `resolve`, `alarms` на входах
`inputs/`. Отказы `domain.shared`, `merge` и `domain.witness` — случаи `m61_*` корпуса главы P/02.1 ([P/02.1 Н1.2б](../../Platform/02-installer/spec/02.1-installer.norms.md)).

```yaml
resolve:   вход {field, unit?, domain}; вывод {value, from} | {groups, from}
alarms:    вход — Н3 alarms; вывод {events, members, complete, sentence}
exit:      0 — вычислено; 2 — вход не по форме (шаги 03/11, 04/15 — @exit 2, словарь М10/01; прочие случаи — чтением); коды выхода — по принципу словаря М11/01 («Коды выхода команд-векторов»: 2 — форма доверенного входа, 0 со словом — документ другого кластера; решение «Архитектора» по сверке М11, H14).
           Не по форме у alarms: имя члена не по грамматике члена, lost_after не > 0, history или свидетель не по форме Н1.9
           и Н1.8 (history без cut_before или с cut_before null — тоже, Н1.9 A13), страница-объект без received_at и sent_at,
           нет received_at или sent_at у члена с отчётом, history строкой, свидетель без ts, witnesses не список, now не
           число, лишнее поле; страница не объект ([], число) или не по форме Н1.7 — 0 unreadable, не 2; page null при
           last_report, received_at и sent_at null у never — 0;
           у resolve: term, rev не целые ≥ 1 (целое по значению: 1.0 = 1, урок 2 Н1), пустое field.name, неизвестный
           field.type, неизвестный merge, при merge union любое из трёх значений (unit, domain.value, inherit) не список —
           даже неиспользованное, значение group_by не список, нет domain или domain без value, unit null или domain.value
           null при union, лишнее поле (добавлено сверкой М11, A18, A19, H14)
```

| № | Сценарий | Нормы |
|---|---|---|
| 01 | стенд: правка — 200; старая `base_rev` — 409; поле не общее, тип, схема — один 400; `m1` берёт документ, `GET /domain/shared/testsub?unit=` с `from`, `union` у `marks`; доставка | Н1.2–Н1.6 |
| 02 | стенд: агент `m2` выключен — в доставке `silent`, строка тревоги `silent` в `/domain/alarms`; вернулся — взял документ | Н1.6, Н1.8 |
| 03 | `resolve`: своё, домена, объединение, спеки, документ, группы, домена нет | Н3 resolve |
| 04 | `alarms`: все ответили; шторм `truncated`; молчит — последний отчёт; свидетель — `not_reporting`; ни разу; страница не читается; история без повторов и `history_cut_before`; окно; `cut_before` 0, строка не `alarm`, повтор в странице, ничья свидетелей (сверка М11, A13, A15–A17) | Н3 alarms, Н1.8, Н1.9 |
| 05 | неподписанный документ, положенный мимо правки: член не берёт — `domain/shared-refused` `not_a_record` (мутационная проверка 2026-10-18) | Н1.2 `signature`, Н3 «взять документ» |
| 06 | указатель с чужой суммой: член не берёт документ — `domain/shared-refused` «does not match the pointer» (мутационная проверка, класс сумм) | Н3 «взять документ» шаг 3 |

---

## Решает реализация

1. **команды `resolve` и `alarms`** — шаблоны с `{input}`;
2. **как агент собирает страницу** — запрос к индексу своей консоли или к ресурсам напрямую, лишь бы форма и фронт Н1.7
   сохранялись.

---

## Чеклист готовности

- Пункт М11/11-01 перенесён в [P/02.1](../../Platform/02-installer/spec/02.1-installer.norms.md) как P/02.1-29 (поздний слой; стадия B; [id-map](../../Platform/common/id-map.tsv); разбор ревью стадии A 8–10, № 11).
- [ ] **М11/11-02** документ Н1.2: форма, подпись выпускающим, указатель, пять объектов, `rev + 1` после переноса — сц. 01; переподпись, объект ревизии не перезаписывается проигравшей правкой (A1) — чтением
- [ ] **М11/11-03** правка Н1.3 по порядку, все отказы одним 400 — сц. 01; `shared.<sub>` не объект, значение под печать, прежний документ не читается — 503 (A6, A7, A9) — чтением
- [ ] **М11/11-04** доставка Н1.4: `doc` только при расхождении, проверка агента, никогда назад, отказ — сц. 01, 02; подделка — урок 10 `record`; форма строк в отчёте и снятие отказа взятым документом (A3, A4) — чтением
- [ ] **М11/11-05** значение при чтении Н1.5 — сц. 01, 03; `?unit=` другой спеки — 404 `no such unit`, чтением (каталог стенда урока 11 — одна спека)
- [ ] **М11/11-06** доставлено скольким Н1.6, `declared` со схемой — сц. 01, 02; до первого документа — сц. 01 шаг 2 (A5)
- [ ] **М11/11-07** страница тревог Н1.7, фронт раз в секунду, срочный отчёт — чтением (стенд тревог не поднимает)
- [ ] **М11/11-08** список Н1.8: состояния, строка молчания, свидетель, строгость страницы, ничья свидетелей — сц. 02, 04; семья свидетелей в отчёте, грамматика since/until (A2, A12) — чтением
- [ ] **М11/11-09** история Н1.9: один писатель, предел, без повторов, в резервной копии урока 10, `cut_before` 0 — сц. 04; писатель и срез (A14) — чтением

## Соответствие прежним урокам

Нормирует то, что рассказывали `М12A_Domain/12-shared-settings-without-a-database.md` (шаги 1–8; шаг 9 — сценарии VMS
— М12) и `М12A_Domain/13-alarms-from-every-member.md` (шаги 1–7). ADR-0010, ADR-0032, решения C6 «точный документ»,
C6 «testsub2». Исторические исходники сохранены в Git.

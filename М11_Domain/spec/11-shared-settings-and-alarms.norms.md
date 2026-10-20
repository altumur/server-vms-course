# М11/11 — Общие настройки и тревоги членов: нормы

Канон урока. [Лекция](../11-shared-settings-and-alarms.md), [HTTP-контракт](11-shared-settings-and-alarms.api.openapi.yaml),
[инструкция](11-shared-settings-and-alarms.README.md), [приёмка](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md).
Перенесено: Н1.2, Н1.3, Н1.4 `carry`/`holder_self`, Н1.6 `domain/view.shared`, Н1.9, сц. 01 — в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8).

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md). Порядок массивов вывода — урок 1 Н0 (общее М11).

## Н1 Форма

**Время.** Поля времени строк и объектов урока — время по [канону Н0](../../Platform/01-store/spec/01.1-store.norms.md#время-в-строке). Объект страницы `domain/alarms` (`from`, `to`) — [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) Н1 «Время» (стадия B; урок 9). Объект истории `domain/alarm-history/<член>` — [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) Н1 «Время» (стадия B; урок 8).

**Данные** ([каталог](../../Platform/common/data/catalog.tsv)):
- владеет: `<sub>/<spec:domain.witness.report>/<имя>` (урок P/10; решение «Архитектора» по планам переноса 8–10, п. 8);
- читает: `domain/holder`, `domain/shared` (строка — P/08.9), `domain/shared-docs/rev-<rev>`, `domain/alarm-history/<член>`, `domain/members/<член>/reports/<rev>`, `domain/members/<член>/reported`.

Строка `domain/shared`, объекты `domain/shared-docs/rev-<rev>` и `domain/alarm-history/<член>` держателя — [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8).
Объект копии `domain/shared` у члена, `domain/shared-refused`, `domain/alarms` — перенесено в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) Н1 «Данные» (стадия B; урок 9).

Общее уроков 1–10 Н1 действует. Домен не знает ни одного поля подсистемы (ADR-0010): что общее, объявляет спека, а
значение домена разрешается **при чтении**, не записью в строки. Тревоги членов домен собирает из их отчётов: к члену он
соединений не открывает. Решение «Архитектора» по вопросам М11/11; C6 «точный документ». Для документа и истории абзац
перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) Н1 (стадия B; урок 8).

### Н1.1 Объявление `domain.shared`

Перенесено в [P/02.1 Н1.2б](../../Platform/02-installer/spec/02.1-installer.norms.md) (стадия B; глава позднего слоя, вводит урок 8).

### Н1.2 Общий документ

Перенесено в [P/08.9 Н1.2](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8).

### Н1.3 Правка

Перенесено в [P/08.9 Н1.3](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8; сторона процесса; дверь консоли домена — строка Н2 ниже до урока P/10).

### Н1.4 Доставка члену

`carry` и `holder_self` (сторона держателя) перенесены в [P/08.9 Н1.4](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-06 (стадия B; урок 8); сторона агента — [P/09.1 Н1.10](../../Platform/09-agent/spec/09.1-agent.norms.md) (стадия B; урок 9).

### Н1.5 Значение при чтении

```yaml
resolve:         функция Н3 — значение поля для единицы: единица → домен → inherit спеки
door:            GET /domain/shared/<sub>[?unit=<id>] у консоли кластера (своя, не пересылается; view) →
                 200 {sub, term, rev, fields: {<имя>: <запись>}} — по каждому элементу domain.shared этой спеки
  record:        поле — {value, from, inherit, merge?} (merge — только union); group_by — {groups, from}; документ — {value, from}
  term, rev:     документа этого кластера: у члена — объект domain/shared (копия, взятая P/09.1 Н3 «взять документ»), у держателя — объект, который
                 называет указатель; документа нет — null, значения — без домена
refusals:        подсистема без domain.shared — 404 {error: "no such shared settings", detail: "'<sub>' shares no field with the
                 domain"}; ?unit= пустой или повторён — 400 {error: "refused", detail: "a unit id is required"} (как урок 1
                 Н4 ?cluster=; добавлено сверкой М11, A11); единицы нет — в том числе единица другой спеки (её разрешает своя
                 консоль; решение «Архитектора» по сверке М11) — или id не по грамматике P/06.1 Н1.3 (в том числе `..` после
                 декодирования) — 404 {error: "no such unit"}; документ не
                 проходит record — значения без домена, journal domain.shared.refused
```

### Н1.6 Доставлено скольким

`domain/view.shared` — перенесено в [P/08.9 Н1.6](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8); `delivery` двери ниже — оно.

```yaml
door:          GET /domain/shared у консоли домена (view) → 200 {doc, delivery, declared}
  doc:         документ как подписан (объект) | null
  delivery:    view.shared
  declared:    {<sub>: [{name, type, schema?}]} — элементы domain.shared спек каталога, по name; schema — у документа
               (КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md §10a, добавлено М11/11; поздний слой P/07 Н1.6)
```

### Н1.7 Страница тревог члена

Перенесено в [P/09.1 Н1.10](../../Platform/09-agent/spec/09.1-agent.norms.md) (стадия B; урок 9).

### Н1.8 Список тревог у держателя

```yaml
door:          GET /domain/alarms?since=&until= у консоли домена (view); умолчание — сутки до now; не конечные числа или
               since > until — 400 {error: "refused", detail: "since and until are times, in seconds"}; число — по
               грамматике числа JSON целиком (без пробелов, «+», «_»), параметр не повторён (добавлено сверкой М11, A12)
answer:        200 {since, until, events, members, complete, sentence} — функция alarms (Н3) на странице последнего отчёта
               каждого члена списка (держатель включён), истории (P/08.9 Н1.9) и свидетелях
member_state:  ok | silent | not_reporting | never | unreadable
  silent:      последний отчёт старше LOST_AFTER (вид урока 1, 45 с); silent_since = последний отчёт + LOST_AFTER
  not_reporting: silent, а свидетель слышал единицу члена позже последнего отчёта
  never:       отчёта не было ни разу
  unreadable:  страница не по форме P/09.1 Н1.10 (у функции alarms — и вход "garbled")
silence_line:  молчащий член — строка тревоги {t: silent_since, kind: silent | not_reporting, class: alarm, member,
               subsystem: "domain", last_report, ongoing: true, alive_at?, alive_via?} — всегда, пока молчит
witness:       domain.witness {report, member_field} (P/02.1 Н1.2б): объекты <sub>/<report>/<имя> = {ts, cluster, units: {<член>:
               секунды с последнего раза}} у кластеров и в отчётах; семья — ключи <sub>/<report>/<имя> (имя после «/»), агент
               несёт каждый объект семьи как объект отчёта (P/09.1 Н1.2 member_objects), объект <sub>/<report> без имени —
               не свидетель (добавлено сверкой М11, A2; сторона агента — P/09.1 Н1.10); member_field — fixed поле единицы, несущее имя члена
               (отказ загрузки — P/02.1 Н1.2б); alive_at = ts − units[член], alive_via = "<cluster>/<имя>"; свидетелей несколько —
               наибольший alive_at среди тех, что позже last_report; при равном — меньший alive_via в байтах UTF-8
               (добавлено сверкой М11, A17)
clock:         время строки страницы на часах домена: t + (received_at − sent_at) последнего принятого отчёта, который
               несёт эту страницу (поля последнего запроса метки, P/08.3 Н1.3); не page.to: прежняя страница в новом отчёте
               старые тревоги вперёд не сдвигает (решение «Архитектора» по R41-16 прогона 41); t_src — t как пришло
events_order:  по t убывая, затем member, id; строки истории — from_history: true
```

### Н1.9 История тревог

Перенесено в [P/08.9 Н1.9](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B; урок 8).

---

## Н2 Двери

HTTP-контракт: [11-shared-settings-and-alarms.api.openapi.yaml](11-shared-settings-and-alarms.api.openapi.yaml). Тело отказа —
`{error, detail}`. Двери `/domain/shared` и `/domain/alarms` консоли домена — строки [договора пересылки](../../Platform/common/contracts/forwarding.md) «Двери домена» (добавлено
М11/11); `/domain/shared/<sub>` — своя у консоли кластера.

| Дверь | Кто | Успех | Отказы |
|---|---|---|---|
| GET `/domain/shared` | консоль домена | Н1.6 | 401/403 |
| PUT `/domain/shared` | консоль домена → процесс `domain` (сторона процесса — [P/08.9 Н2](../../Platform/08-domain/spec/08.9-domain.norms.md)) | `{term, rev, by}` | P/08.9 Н1.3 |
| GET `/domain/shared/<sub>[?unit=]` | консоль кластера | Н1.5 | Н1.5 |
| GET `/domain/alarms?since=&until=` | консоль домена | Н1.8 | 400; 401/403 |

---

## Н3 Проход

### взять документ (агент члена, после записи срока урока 10)

Перенесено в [P/09.1 Н3](../../Platform/09-agent/spec/09.1-agent.norms.md) «взять документ» (стадия B; урок 9).

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
вход:   {now, since, until, lost_after, members: {<член>: {last_report: <часы домена> | null, received_at, sent_at, page: <P/09.1 Н1.10> |
         "garbled" | null, history: <P/08.9 Н1.9> | null}}, witnesses: [{sub, name, ts, cluster, units}]}
1. каждый член:
   last_report нет и page нет                         → never
   last_report нет, а page есть                       → вход не по форме (код 2): страница приходит только с отчётом
   page = "garbled" или не по форме P/09.1 Н1.10      → unreadable; не по форме — и строка без id, class ≠ alarm, kind
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

**Гонки.** Член без связи и шторм тревог — перенесено в [P/09.1 Н3](../../Platform/09-agent/spec/09.1-agent.norms.md) «Гонки» (стадия B; урок 9). Правка и перенос — [P/08.9 Н3](../../Platform/08-domain/spec/08.9-domain.norms.md) «Гонки» (стадия B; урок 8).

---

## Н4 Отказы

| `error` | Код | Когда |
|---|---|---|
| `refused` | 400, 409, 413, 503 | правка — [P/08.9 Н4](../../Platform/08-domain/spec/08.9-domain.norms.md); окно `/domain/alarms`; `?unit=` пустой или повторён (Н1.5) |
| `standby` | 503 | процесс `domain` — ждущий (P/08.10 Н1.7) |
| `no such shared settings` | 404 | подсистема без `domain.shared` |
| `no such unit` | 404 | `?unit=` нет такой единицы, в том числе единица другой спеки (решение «Архитектора» по сверке М11) |
| `frozen`, `deposed` | 503, 409 | [P/08.8](../../Platform/08-domain/spec/08.8-domain.norms.md) Н1.6, Н1.7 |

---

## Н5 Приёмка

Каталог `Source/tests/testdata/acceptance/М11_Domain/11/` ([README](../../Source/tests/testdata/acceptance/М11_Domain/11/README.md)):
сц. 02 — стенд урока 3 (каталог `testsub`: поля `step`, `marks`, документ `rounds`); сц. 01 перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) Н5
(стадия B; урок 8); команды `resolve`, `alarms` на входах
`inputs/`; сц. 05, 06 перенесены в [приёмку P/09.1](../../Platform/09-agent/acceptance/1/README.md) как 05, 14, вход `shared-doc-unsigned.json` — туда же
(стадия B; урок 9). Всего 3 сценария / 37 шагов. Отказы `domain.shared`, `merge` и `domain.witness` — случаи `m61_*` корпуса главы P/02.1 ([P/02.1 Н1.2б](../../Platform/02-installer/spec/02.1-installer.norms.md)).

```yaml
resolve:   вход {field, unit?, domain}; вывод {value, from} | {groups, from}
alarms:    вход — Н3 alarms; вывод {events, members, complete, sentence}
exit:      0 — вычислено; 2 — вход не по форме (шаги 03/11, 04/15 — @exit 2, словарь М10/01; прочие случаи — чтением); коды выхода — по принципу «Стенда домена» общего README приёмки («Коды выхода команд-векторов»: 2 — форма доверенного входа, 0 со словом — документ другого кластера; решение «Архитектора» по сверке М11, H14).
           Не по форме у alarms: имя члена не по грамматике члена, lost_after не > 0, history или свидетель не по форме P/08.9 Н1.9
           и Н1.8 (history без cut_before или с cut_before null — тоже, P/08.9 Н1.9 A13), страница-объект без received_at и sent_at,
           нет received_at или sent_at у члена с отчётом, history строкой, свидетель без ts, witnesses не список, now не
           число, лишнее поле; страница не объект ([], число) или не по форме P/09.1 Н1.10 — 0 unreadable, не 2; page null при
           last_report, received_at и sent_at null у never — 0;
           у resolve: term, rev не целые ≥ 1 (целое по значению: 1.0 = 1, урок 2 Н1), пустое field.name, неизвестный
           field.type, неизвестный merge, при merge union любое из трёх значений (unit, domain.value, inherit) не список —
           даже неиспользованное, значение group_by не список, нет domain или domain без value, unit null или domain.value
           null при union, лишнее поле (добавлено сверкой М11, A18, A19, H14)
```

| № | Сценарий | Нормы |
|---|---|---|
| 02 | стенд: агент `m2` выключен — в доставке `silent`, строка тревоги `silent` в `/domain/alarms`; вернулся — взял документ | Н1.6, Н1.8 |
| 03 | `resolve`: своё, домена, объединение, спеки, документ, группы, домена нет | Н3 resolve |
| 04 | `alarms`: все ответили; шторм `truncated`; молчит — последний отчёт; свидетель — `not_reporting`; ни разу; страница не читается; история без повторов и `history_cut_before`; окно; `cut_before` 0, строка не `alarm`, повтор в странице, ничья свидетелей (сверка М11, A13, A15–A17) | Н3 alarms, Н1.8, P/08.9 Н1.9 |

Сц. 05 и 06 перенесены переносом урока 9 в [приёмку P/09.1](../../Platform/09-agent/acceptance/1/README.md) как 05 и 14
(стадия B).

---

## Решает реализация

1. **команды `resolve` и `alarms`** — шаблоны с `{input}`;
2. перенесено в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) «Решает реализация» п. 7 (стадия B; урок 9).

---

## Чеклист готовности

- Пункт М11/11-01 перенесён в [P/02.1](../../Platform/02-installer/spec/02.1-installer.norms.md) как P/02.1-29 (поздний слой; стадия B; [id-map](../../Platform/common/id-map.tsv); разбор ревью стадии A 8–10, № 11).
- Пункт М11/11-02 перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-01 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М11/11-03 перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункты М11/11-04, -07 перенесены в [P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) как P/09.1-12, -13 (стадия B; урок 9; [id-map](../../Platform/common/id-map.tsv)); сторона держателя М11/11-04 — [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-06 (стадия B).
- [ ] **М11/11-05** значение при чтении Н1.5 — P/08.9 сц. 01, сц. 03; `?unit=` другой спеки — 404 `no such unit`, чтением (каталог стенда урока 11 — одна спека)
- Пункт М11/11-06 перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)); дверь `GET /domain/shared`, `declared` — Н1.6 `door` здесь до урока P/10 (P/10-14).
- [ ] **М11/11-08** список Н1.8: состояния, строка молчания, свидетель, строгость страницы, ничья свидетелей — сц. 02, 04; семья свидетелей в отчёте, грамматика since/until (A2, A12) — чтением (М11/11-08 → P/10-06; было P/08.9-04; план урока 8 В2)
- Пункт М11/11-09 перенесён в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) как P/08.9-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).

## Соответствие прежним урокам

Нормирует то, что рассказывали `М12A_Domain/12-shared-settings-without-a-database.md` (шаги 1–8; шаг 9 — сценарии VMS
— М12) и `М12A_Domain/13-alarms-from-every-member.md` (шаги 1–7). ADR-0010, ADR-0032, решения C6 «точный документ»,
C6 «testsub2». Исторические исходники сохранены в Git. Н1 «Время» (история) и вводный абзац Н1, Н1.2, Н1.3, Н1.9 целиком,
Н1.4 `carry` и `holder_self`, Н1.6 `domain/view.shared`, строка Н2 `PUT /domain/shared`, строки Н4 правки, «Гонки» Н3 о
правке и переносе, сц. 01 и пункты М11/11-02, -03, -06, -09 (часть -04) перенесены в [P/08.9](../../Platform/08-domain/spec/08.9-domain.norms.md) (стадия B, урок 8). Н1 «Время» (страница),
владение копией `domain/shared`, `domain/shared-refused`, `domain/alarms`, Н1.4 `member`, `in_report`, Н1.7, Н3 «взять документ»,
«Гонки» о члене без связи и шторме, сц. 05, 06 (там 05, 14), п. 2 «Решает реализация» и пункты М11/11-04, -07 перенесены в
[P/09.1](../../Platform/09-agent/spec/09.1-agent.norms.md) (стадия B, урок 9).

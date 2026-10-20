# М10/9 — Консоль: нормы

Канон Н1.4, Н1.5 и пунктов М10/9-06, -07 — модуль консоли и его контракт с оболочкой — до переноса урока 7 (стадия B).
[Лекция](../09-the-console.md), [инструкция](09-the-console.README.md). Своего HTTP-контракта и приёмки у урока больше нет:
двери консоли — [06-console.api.openapi.yaml](../../Platform/06-console/spec/06-console.api.openapi.yaml), приёмка — [P/06.5](../../Platform/06-console/acceptance/5/README.md) и [P/06.3](../../Platform/06-console/acceptance/3/README.md).
Остальное перенесено: Н1.1, Н1.2, Н2 (с `GET /spec`), Н3, строки Н4, сц. 01, 02, 04–12 Н5, пп. 1–3, 5–7 «Решает
реализация», пункты М10/9-01, -02, -08…-15 — в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md); Н1.3, строки Н4 сторожевой и сессии, сц. 03, п. 4
«Решает реализация», пункты М10/9-04, -05 — в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) (стадия B). После переноса урока 7 файл снимается целиком.

## Н0 Словарь слов

Нормативные слова — по [канону курса](../../НОРМАТИВНЫЕ-СЛОВА.md).

## Н1 Форма

**Данные.** Строк хранилища у урока не осталось: владение `door/signer`, `door/keys` и чтения консоли — [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md),
записи строк управления — [P/06.6](../../Platform/06-console/spec/06.6-console.norms.md) (стадия B).

### Н1.1 Три части

Перенесено в [P/06.5 Н1.1](../../Platform/06-console/spec/06.5-console.norms.md) (стадия B); вызовы модуля и его контракт с оболочкой — Н1.4, Н1.5 ниже.

### Н1.2 `display`, `servers`, `console`

Перенесено в [P/06.5 Н1.2](../../Platform/06-console/spec/06.5-console.norms.md) (стадия B).

### Н1.3 Сторожевая

Перенесено в [P/06.3 Н1.3](../../Platform/06-console/spec/06.3-console.norms.md) (стадия B); `via` и его значения — там же.

### Н1.4 Что зовёт модуль — закрытый список

```yaml
reads:   /session, /spec, /<sub>/spec, /mounts, /<rows>, /<sub>/<rows>, /<sub>/<table> (только из servers.show; добавлено М10/10),
         /where/<id>, /<sub>/where/<id>, /servers, /unplaceable, /<sub>/unplaceable, /policy, /drain, /schema (добавлено М10/10),
         /events, /metrics (только running_gauge и workers_gauge), /domain/* (М11/8 Н1.2), /api/held (М11/8 Н1.9, форма — М11/10 Н1.4), /domain/shared/<sub> (М11/11 Н1.5)
writes:  POST/PUT/DELETE /<rows>[/<id>] и /<sub>/<rows>[/<id>], POST /marks, PUT /policy, POST/DELETE /drain, GET/PUT/DELETE /servers/<s>/labels,
         POST/DELETE /servers/<s>/decommission, /domain/* (М11/8 Н1.2), POST/DELETE /session, /session/break-glass, login_url
never:   /{sub}/requests, /api/backup (М11/10), /resources, /{sub}/{table} вне show, двери держателей (door из where — только оболочке)
order:   /session → /spec → /mounts → по подсистеме /<rows> → /servers → /unplaceable → /domain/shared/<sub> (М11/11 Н1.5) → /drain → /schema
         → /domain (+ /domain/alarms; М11/11 Н1.8) → /api/held (М11) → /metrics; опрос каждые poll_s; /events?unit= выбранной — каждые 5 с
```

### Н1.5 Контракт модуля с оболочкой

```yaml
version:   console.version — целое версии API оболочки (P/06.5 Н1.1); проверяется до использования модуля
objects:   ref: unit:<sub>/<id> | server:<s> | worker:<sub>/<w> | member:<m> | domain | person:<name> | group:<sub>/<поле>/<путь>
           | <prefix>:<…> оболочки (модуль только хранит)
api:       console.api(method, path, body) → ответ | throw {status, body, retry}
           POST с памятью повторов владельца (единица/просьба) — один ключ на логическое действие, не на одинаковые байты;
           повторы этого действия сохраняют ключ и исходное тело. Новый вызов — новый ключ. Сеть/таймаут 20 с/5xx/
           409 in flight допускают повтор по правилам владельца (2, 3, 5 с или retry_after); 401 → окно входа.
           PUT и таблицы без памяти повторов автоматически не повторяются: при неизвестном исходе сначала чтение.
           Завершённый ответ закрывает действие; отказ до памяти заявки разбирается по контракту владельца, не кэшируется как успех
may:       console.may(cap, ref) → bool по grants сессии (* | unit:); true без grants только при open: true; в закрытой/неизвестной сессии отсутствие grants — false; сервер проверяет всегда
events:    on("select", (ref, obj)) | on("refresh", {units, servers, domain}) | on("logout")
where:     where(ref) → {worker, server, door: {url, token, expires, routes} | null, reason}
           библиотека превращает отсутствующее поле door HTTP-ответа в null для оболочки; HTTP Where остаётся формой контракта P/06 (глава 6.5)
words:     display(name), spec(name), kindWord(e), eventNote(e), addEventNote; W — словарь модуля ru | en
adds:      addSection{id, label, icon, after, off, render}, addTab(kind, {id, label, render, busy}) kind ∈ unit | server |
           worker | member | domain, addTreeNodes(kind | servers | server, fn) → узлы {ref, label, icon, count, kids, badge,
           tags, dot, title, off, open, after, replaces}, addCard(prefix, render), addMenu, addDecor{icon, badge, title},
           addFieldEditor(kind, field, render(host, ref, obj, value, set)), addBlock("server", {id, covers, render}),
           addAction, addNote, addIcons, icon, unitForm(host, ref), dialog(title, fields, ok), confirm, toast, select,
           selected, refresh, logout, fullScreen, isFav, toggleFav
cards:     разметка карточки: <h1>, nav.pc-tabs, <h2> → .card, button.pc-hdbtn, span.pc-crumbs[data-crumbs], p.pc-hdsub
commands:  вид command / command.failed — слово и заметка модуля (action · исход · ответ · «кто: by»; late → «поздно»)
```

---

## Н2 Двери

Перенесено в [P/06.5 Н2](../../Platform/06-console/spec/06.5-console.norms.md) (стадия B), в том числе «Разбор запроса консоли», «Полные формы и границы Н2» и `GET /spec`;
двери сессии — [P/06.3 Н2](../../Platform/06-console/spec/06.3-console.norms.md). HTTP-контракт — [06-console.api.openapi.yaml](../../Platform/06-console/spec/06-console.api.openapi.yaml). Своих дверей у модуля нет: что он зовёт — Н1.4.

---

## Н3 Проход

Перенесено в [P/06.5 Н3](../../Platform/06-console/spec/06.5-console.norms.md) (стадия B): «запрос → ответ», «/servers», «`/where/<id>`», «`/where/<table>/<place>`», «/metrics».

---

## Н4 Отказы

Строки дверей, общих кодов, тела, полос и `GET /spec` перенесены в [P/06.5 Н4](../../Platform/06-console/spec/06.5-console.norms.md); строки сторожевой и сессии (аварийный
вход, не личность, гранта нет, нет домена — не петля, ключи были, чужой Origin, `/session` у открытой консоли) — в
[P/06.3 Н4](../../Platform/06-console/spec/06.3-console.norms.md) (стадия B). У Н1.4, Н1.5 своих HTTP-отказов нет.

---

## Н5 Приёмка

Сценарии 01, 02, 04–12, проверки чтением и сверка python и go М10/6–11 перенесены в [приёмку P/06.5](../../Platform/06-console/acceptance/5/README.md), сценарий 03 и
проверки сторожевой с доменом — в [приёмку P/06.3](../../Platform/06-console/acceptance/3/README.md) (стадия B). Своей приёмки у урока нет.

Модуль (Н1.4, Н1.5) проверяется чтением и jsdom-тестом модуля `Source/tests/console`, без сценариев: TSV говорит с дверями и
страницу не исполняет; модуль у всех реализаций один (ADR-0005), поэтому свидетельство одно.

---

## Решает реализация

Реализация обязана назвать в своём описании:

1. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 1 (стадия B);
2. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 2 (стадия B);
3. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 3 (стадия B);
4. перенесено в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) «Решает реализация» п. 1 (стадия B);
5. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 4 (стадия B);
6. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 5 (стадия B);
7. перенесено в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) «Решает реализация» п. 6 (стадия B).

---

## Чеклист готовности

- Пункт М10/9-01 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-02 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-04 перенесён в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) как P/06.3-02 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-05 перенесён в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md) как P/06.3-03 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- [ ] **М10/9-06** закрытый список вызовов модуля Н1.4 и порядок загрузки — проверяется чтением: вызовы модуля и их порядок — по Н1.4 `reads`/`writes`/`never`/`order`; причина — модуль один у всех реализаций, двери порядок загрузки не показывают
- [ ] **М10/9-07** контракт оболочки Н1.5: `api` с ключом логического действия и повторами только по контракту владельца, `where` с `door`, вызовы библиотеки, без хуков и чужого DOM — проверяется чтением: тест оболочки (jsdom; предмет — поведение страницы, не двери); причина — TSV говорит с дверями, страницу не исполняет
- Пункт М10/9-08 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-04 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-09 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-05 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-10 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-06 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-11 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-07 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-12 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-08 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-13 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-09 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-14 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-10 (стадия B; [id-map](../../Platform/common/id-map.tsv)).
- Пункт М10/9-15 перенесён в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md) как P/06.5-01 (стадия B; [id-map](../../Platform/common/id-map.tsv)).

## Соответствие прежним урокам

Нормирует `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` (контракт модуля — разделы 1–10 как Н1.1, Н1.4, Н1.5; раздел 10a — М12A; расхождения контракта с кодом сняты в пользу урока: имя оболочки `<sub>.shell.html`, список вызовов модуля дополнен `/schema`, `/unplaceable`, `/policy`, `/servers/<s>/labels`), `М10A_Platform/15-SpecConsole.md` (шаги 1, 3, 6, 8 (коды), 9–14: описание, чтения, `/servers`, `/metrics`, объявленное, сторожевая, ключ, монтирование; шаг 4 — урок 3; 7 — урок 8), `М10A_Platform/16-HTML.md` (целиком: страница, модуль, слова, наложение, форма, `api`, вызовы оболочки, CSP). Исторические исходники сохранены в Git; контракт модуля остаётся описанием публичной поверхности до переноса `W` и разметки в урок.

Стадия B: из М10/2 перенесены дверь `GET /spec` (Н2 «GET /spec», строка Н4, схемы `SpecView`, `FieldView`, `JsonValue`, `ConsoleRefusal` и общие отказы контракта) и пункт М10/2-15 → М10/9-15 — временно, до переноса урока 6 (глава 6.5); P/02.1-26 снят: слова `display`, `servers`, `console` в загрузчике — P/02.1-26, отдача `display` как написано — в М10/9-15. Строка `door/keys` о проверяющем (Н3 «`/where/<id>`») и проверка токена держателем — часть М10/9-09 — перенесены в [P/03.4](../../Platform/03-worker/spec/03.4-worker.norms.md) Н3 «токен двери у держателя», P/03.4-08 (стадия B).

Стадия B, урок 6: Н1.1, Н1.2, Н2, Н3, строки Н4, сценарии 01, 02, 04–12, пп. 1–3, 5–7 «Решает реализация», пункты
М10/9-01, -02, -08…-15 перенесены в [P/06.5](../../Platform/06-console/spec/06.5-console.norms.md); Н1.3, строки Н4 сторожевой и сессии, сценарий 03, п. 4 «Решает
реализация», пункты М10/9-04, -05 — в [P/06.3](../../Platform/06-console/spec/06.3-console.norms.md); собственный OpenAPI урока слит в
[06-console.api.openapi.yaml](../../Platform/06-console/spec/06-console.api.openapi.yaml) ([id-map](../../Platform/common/id-map.tsv)). Здесь до переноса урока 7 — Н1.4, Н1.5, М10/9-06, -07.

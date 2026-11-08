# Векторы инструментов и проверки плана — V/11.10, V/11.11

Векторы главы 10 (инструменты чтения, ответ админу) и главы 11 (план, сверка слов, вопрос и отказ) урока V/11. Их
исполняет драйвер `backend` (V/11.7 N5) с данными харнеса [`harness/`](../../../harness/) и заглушкой консоли по
файлу консоли ниже. Модели в векторах нет: вызовы инструментов даны готовыми.

Текст производный от `vectors/plan-check/README.md`, руками не правится: источник — английский [`vectors/plan-check/README.md`](../../../vectors/plan-check/README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

## Файлы

| Файл | Что |
|---|---|
| `stand3.console.json` | консоль стенда 3 пилота: засев и манифесты обзора пакета передачи в форме дверей консоли урока (V/11.10 N1.2) |
| `vms.console.json` | консоль VMS: манифесты канона `cam` и `rec` проекцией `ManifestView`, несколько камер, поток, записи; у админа `admin` на `*` |
| `text.json` | сверка слов V/11.11 N1.2 — функция, аргументы, ожидание; `said` — выражения `rights`, `not_found`, `all` над `norm`, с русскими словами у границ (ADR-0093 доп. (28), (29)) |
| `cases.json` | ходы: тексты хода, секреты, вызовы инструментов по порядку и ожидаемый результат каждого |

## Консоль (`<name>.console.json`)

Охват, корень и манифесты `backend` берёт по V/11.10 N0, N1.2: охват — подсистемы консоли
(или `subs` случая), корень — `mounts.root`, манифест — `manifests[<sub>]`; «в охвате ли» — есть ли подсистема в
консоли.

```yaml
mounts:     {root, mounts: {<sub>: ManifestView}} — the root and the subsystems of the console
manifests:  {<sub>: ManifestView} — copies of the module
rows:       {<sub>: [element configured]} — GET /<rows> at the root, GET /<sub>/<rows> at another one: {rows: [], configured: …}
tables:     {<sub>: {<table>: [row]}} — GET /<table> at the root, GET /<sub>/<table>: {<table>: […]}
session:    the module session — for may() of the stub (the page does not read it)
schema:     the answer of GET /schema
```

Иной путь — 404 `{error: "no_route"}`. `may(cap, ref, sub)` заглушки — правило модуля (P/07 N1.5): аварийная сессия
(`via: break-glass`) и открытый режим — да; иначе грант ранга не ниже `cap` с областью `*`, `unit:<sub>/<id>` единицы или
её `about`-единицы, `labels:<…>` — все метки есть у `about`-единицы, если она есть, иначе у самой единицы (правило
`covers` модуля). Право записи — `may("admin", …)`
(V/11.10 N1.2).

Отличия от стенда пилота: гранты `edit` подняты до `admin` (дверь записи строки единицы требует `admin`, ADR-0093 доп. (4)
п. 4); подписи полей и слова операторов пилота лежат в `display` манифестов (`fields`, `field_help`), а не накладкой;
не заданное поле без умолчания — `null`.

## Ход (`cases.json`)

```yaml
id:        the case name
console:   the console name — the file <name>.console.json
rule:      the norm rule the case holds (or «replay of the pilot base: <set> <request> (<kind>)» — <set> is the set, <request> the request, <kind> the kind)
violates:  present — the case is «violated but passes»: the check lets it through, the reason in words (a measurement gap, the lesson README)
source:    lesson — a lesson case; pilot <set> <request> — calls of the pilot's base run
texts:     the texts of the turn (V/11.9 N0): the request, then the admin's answers
secrets:   numbers of the secrets entered in the turn (V/11.12 N1.3); absent — there are no secrets
session:   the fields that replace the session of the console (grants, an emergency session)
fail:      {<path>: <status>} — these console reads answer with the status with {error: "unavailable", detail: "test"}
subs:      the scope — the subsystems of the page, if not all subsystems of the console
bulk:      {<sub>: N} — the rows of the subsystem are padded to N with copies of the first row: id bulk-1, bulk-2, …, the name field (if the id
           of the manifest is not numeric) — the same id, revision 1 (the boundary LIST_MAX, V/11.10 N1.2)
calls:     [{name, args, content}] — the calls in order in one turn; content — the expected content of the result (V/11.10 N1.3)
```

Ход — один на случай: учёт найденного за ход (`find_units` → проверка `refuse`) и «раз за ход» (проверка «не найдено»)
идут по вызовам случая. Сравнение `content` — байт в байт. Цикл хода (подсказки, «сначала данные», `not executed`,
предел) — не здесь: векторы `turn` (V/11.9 N5).

## Откуда ожидания

- **Переигровка основы пилота** (`source: pilot …`): все вызовы инструментов шести наборов стенда 3 прогона основы
  (v4.0 + `tool_choice: required`), кроме подсказки цикла «сначала данные». Перевод формы урока: слот секрета пилота —
  метка `{"secret": 1}`, пароль убран из текста просьбы (он — в поле формы). Вердикт совпадает с вердиктом пилота
  в 174 вызовах из 175; расходится L07 — `named: ["Spruce"]` при просьбе «Remove the label floor2 from all counters»:
  правило `named` (ADR-0093 доп. (4) п. 5) отвергает план, который пилот принимал (README урока, «Правки после замера»).
- **Случаи урока** (`source: lesson`): каждое правило V/11.10 N1.5 и V/11.11 N1.3–N1.5 — хотя бы раз «нарушено» и «не
  нарушено»; формы «нет прав» по одной; классы «нарушено, но проходит» — с `violates`. Случаи `vms-*` — русские просьбы
  по манифестам VMS с подписями `display` и словами операторов `words.json`: «Выключи» называет «Включена», подмена поля
  отвергается; `vms-passes-days` — «дней» называет и `retention_days`, и `min_depth_days` (`violates`).
- Каждый `op` V/11.10 N1.5 вызывается в аргументах корпуса (генератор векторов это проверяет); `gte` и `lt` — на
  меньшем, равном и большем значении.
- `content` построен снятым ядром страницы и сверен с нормой построчно; правка нормы или харнеса меняет векторы тем же
  коммитом.

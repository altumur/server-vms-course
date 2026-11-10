# D3 — формы ожидания: `!contains` и `$name` внутри JSON ожидания

**Случаев:** 4 «раннер GREEN, движок нет» — door 2, inproc 2 (`18-no-echo:86`, `21-rights:107`). Ворота добавляются в P01.125.

## Суть
Движок ставит `red implementation`, причина `expectation`, двум шагам, которые раннер засчитывает:
- `18-no-echo` 1, строка 86: запрос `POST /v1/write {"op":"put",…,"cas":"424242424242"}`, ожидание `409 {"kind":"conflict","index":"","error":"!contains 424242424242"}` — поле `error` не должно содержать подстроку;
- `21-rights` 6, строка 107: `GET /v1/list?prefix=other/21-rights/`, ожидание `200 {"keys":{"other/21-rights/c9":"$v"}}` — значение сравнивается со связанным раньше `$v`.

## Норма
`Platform/common/acceptance/README.md`, таблица «Expectation»:
- строка 315: «`!contains text` | a string value does not contain the substring»;
- строка 309: «`$name` | binds a JSON string or number …; the first occurrence binds, the following ones compare»;
- строка 308: «`<code> <JSON>` | in P/01.1 — JSON whole (the order of the object fields does not matter) …».

## Образцы
| Шаг | Движок (`out/P_01_1_door/engine.json`) | Раннер (`acc/P_01_1_door/P-01.1-door.json`) |
|---|---|---|
| `18-no-echo:86` | `red`, class `implementation`, reason `expectation` | step 1, line 86, `ok: true` |
| `21-rights:107` | `red`, class `implementation`, reason `expectation` | step 6, line 107, `ok: true` |
| то же в inproc | `out/P_01_1_inproc/engine.json` | `acc/P_01_1_inproc/P-01.1-inproc.json`, `ok: true` |

## Код движка
`internal/engine/scenario_verdict.go:481–505` (`matchScenarioExpectation`): после кода — либо `~` (подстрока всего тела), либо строгий JSON (`strictjson.Decode`) и сравнение; формы значений поля `"!contains …"` и `"$name"` внутри JSON сравниваются дальше функцией сравнения JSON (за `scenario_verdict.go:505`), где, судя по исходу, строка `"!contains 424242424242"` и `"$v"` берутся как буквальные значения. Привязки в ожидании ищутся в `scenario_verdict.go:285` и `319` (`bindings[…]`) — для ли этих полей, по отчёту не видно.

## Мнение представителя
Исход — **движок**: формы 309, 315 однозначны. Главная причина — модель; вторая — **цикл**: ворота `compare` по доп. (9) берут только буквальные `expect` (заглушка отвечает буквальным значением), а ожидания с формами значений (`!contains`, `$name`, `~`, `@any`, `@not(…)`) ворота не проверяют. Правило для P01.125 (предлагаемое): заглушка на части шагов с формой значения в ожидании отвечает значением, удовлетворяющим форме, и значением, нарушающим её (для `!contains` — с подстрокой; для `$name` — равным/не равным связанному); первое должно быть GREEN, второе — нет.

## Вопросы ревьюеру
1. `!contains text` внутри JSON-ожидания относится к значению поля (строка 315) — подтверди, что раннер прав, а не что это форма только для тела (316–317).
2. Подходит ли правило для ворот; какие ещё формы значений включить сразу?

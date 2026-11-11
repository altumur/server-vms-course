# E2 — «JSON целиком» без правила `error` главы 1: неназванное поле `error` в корне отказа — red

**Случаев:** 188 из 189 красных шагов цели `P/01.1/inproc`, 35 сценариев: 02, 04, 06, 07, 09–22, 24–40. Больше всего: 38-batch-form 35, 28-admission 13, 32-validation-order 12. Движок: `result red, class implementation, reason expectation` у всех.

## Суть
Кандидат отвечает отказом с правильным кодом и правильными полями, но добавляет обязательное по норме M поле `error` с текстом. Движок сравнивает тело с ожиданием «целиком» и считает `error` лишним полем.

Повтор (`/srv/calib-p0180/p0126/tmp/replay127/replay.json`, 345 шагов через адаптер двери кандидата):
- в 188 красных шагах после удаления одного поля `error` из корня ответ совпадает с ожиданием: код, поля, значения, привязки `$name`;
- у 150 из 151 зелёного шага движка повтор совпадает и без поправки; шаг 86 (18-no-echo) — форма `!contains` внутри `error`, повтор её не разбирает.

Образцы:
| Строка | Запрос | Ожидание | Ответ кандидата |
|---|---|---|---|
| 5 (02-create-once:2) | `POST /v1/write {"op":"put",…,"cas":""}` | `409 {"kind":"conflict","index":"$a"}` | `409 {"kind":"conflict","error":"operation refused","index":"1"}` |
| 54 (12-id) | `POST /v1/write {…,"id":"0123…"}` | `400 {"kind":"badrequest"}` | `400 {"kind":"badrequest","error":"operation refused"}` |
| 40 (09-guard:4) | `POST /v1/write {…,"guard":{…}}` | `412 {"kind":"guard","key":"acc/09-guard/slots/w-1","index":"$s2"}` | `412 {"kind":"guard","error":"operation refused","index":"20","key":"acc/09-guard/slots/w-1"}` |
| 73 (15-too-large) | `POST /v1/write` с `@big(524288)` | `413 {"kind":"toolarge","key":…,"size":524292,"limit":524288}` | то же + `"error":…` |

## Норма
- J: `Platform/01-store/acceptance/1/README.md:16`: «`expect` is `<code> <JSON body>`; the JSON is compared whole; `error` is compared only if it is named: its text is not normed. An unnamed `error` is admitted only in the root of the body; an extra field elsewhere is a mismatch.»
- J: README общей приёмки:308 — «in P/01.1 — JSON whole» (общая форма; уточнение главы 1 — строка 16 выше).
- M (видела модель): `01-store/spec/01.1-store.norms.md`, P/01.1-R025: «`error` is required in a refusal, although acceptance usually does not compare its text»; R026: «a refusal | `kind`, `error` and the fields of its N4 row».

## Код движка
`engine/internal/engine/scenario_verdict.go:498–530`, `matchScenarioExpectation`: тело ожидания и ответа декодируется и сравнивается `matchScenarioValue(expected, actual, …, subset = !whole)`; при `whole` любое лишнее поле — несовпадение. Исключения для `error` нет: в коде движка поиска `"error"` в сравнении сценариев — 0 совпадений.

## Мнение представителя
Исход — **движок**: правило главы 1 однозначно, кандидат следует норме M. Главная причина — модель (линия судьи): правило лежит в README главы, а не в общем словаре, и движок его не применил. Вторая — **цикл**: заглушка ворот P01.107/P01.114/P01.125 отвечает телом ожидания байт в байт, без `error`, поэтому правило никогда не проверялось.

Правило для ворот: заглушка на отказе добавляет неназванное `"error":"<любой текст>"` в корень — шаг обязан быть GREEN; то же поле во вложенном объекте — red.

## Вопросы ревьюеру
1. Правило строки 16 записано в README главы 1, а не в общем словаре: это «норма» (место правила) или «движок» (движок обязан читать README главы)?
2. Повтор с поправкой даёт 344 из 345. Нужен ли зачётный перепрогон inproc после правки движка, чтобы заменить вывод повтора вердиктом?

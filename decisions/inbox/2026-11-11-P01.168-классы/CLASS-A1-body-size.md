# A1 — правило `size` отказа по телу (сц. 22) движок не исполняет: верный ответ кандидата — red

**Случаев:** 2. P/01.1/door и P/01.1/inproc, `Platform/01-store/acceptance/1/scenarios.tsv:111` (сц. `22-body-edge`, шаг 1): тело 4194364 байта (`@big(4194304)`), ожидание `413 {"kind":"toolarge","limit":1048576}`. Шаг 2 той же строки (`GET`, `items:null`) — GREEN.

## Наблюдение движка
`engine.json` обеих целей: `red`, `class: implementation`, `reason: expectation`. Транспорт прошёл: при обрыве было бы `stand transport` (`scenario_verdict.go:144–147`).

Сравнение — `matchScenarioValueRules` (`internal/engine/scenario_verdict.go:607–630`): в режиме `whole` поле ответа, которого нет в ожидании, допускается только из `rootFields`. `rootFields` собирает `chapterRootBodyFields` (`:555–576`) по одной фразе `rootBodyPattern` (`:25`): «An unnamed `<name>` is admitted only in the root of the body». Для главы 1 это только `error`. Особого правила для `size` в движке нет: `grep size|4194364` по `internal/` пуст.

**Повтор replay188** (`/home/pilot/owner-receipts/P01.188-court-claude-20261111/replay188/``trace/P_01_1_door.jsonl`, `trace/P_01_1_inproc.jsonl`; итоги шагов совпали с диагностикой):

| Цель | Строка | Запрос движка | Статус | Тело |
|---|---|---|---|---|
| door | `acceptance/1/scenarios.tsv:111` | `POST /v1/write {"op":"put","key":"acc/22-body-edge/c1","items":{"blob":"<x*4194304>"}}` (4194364 байта) | 413 | `{"kind":"toolarge","error":"the body is larger than the body limit","limit":1048576,"size":4194364}` |
| inproc | то же | то же, через `adapters.door` | 413 | то же |
| door, inproc | `:112` | `GET /v1/get?key=acc/22-body-edge/c1` | 200 | `{"items":null,"index":""}` — GREEN |

Сверка с `:111` (`413 {"kind":"toolarge","limit":1048576}`) и README главы 1:16–22. Статус, `kind` и `limit` совпадают. `error` допущен в корне (README:16). `size` — целое число 4194364, это полный размер отправленного тела: README:19–21 и «Original passage 5» `README.cases.md`. `key` нет, других полей нет. По норме ответ верен. Red даёт одно поле `size`: движок не исключил его из сравнения. stderr демона door (`stderr/P_01_1_door.txt`) показывает обычный старт и останов.

## Норма
- M и J одинаково, `Platform/01-store/spec/01.1-store.norms.md:297–298` (M): «If the full size of the body is known, the body refusal MAY contain `size` with this size in bytes».
- `forms/refusals.tsv:19`: `body_limit … 413 toolarge limit,size?`.
- J, `Platform/01-store/acceptance/1/README.md:19–22` (тот же файл есть в M): «Only for a body refusal the optional field `size` is admitted: if it is present, it is the integer JSON number of the full size of the sent body … After it is checked it is excluded from the comparison with `expect`».
- J, `common/acceptance/README.md:333`: в режиме `whole` неназванное поле — несовпадение, «except where the README of the first directory of the routing row admits it — by a line «An unnamed `<name>` …» **or by a special comparison rule of that README**».
- Строго к сц. 22 шаг 1 правило сужает `README.cases.md` (только J), «Original passage 5»: число 4194364.

## Код кандидата
- `01-store/internal/httpd/parse.go:202–206`: `readFixed` при `Content-Length` больше предела возвращает `overLimit{size: n, known: true}` до чтения тела.
- `01-store/internal/httpd/server.go:192–203`: `inputError` кладёт `limit` и, если размер известен, `size`, затем делает ограниченный слив.
- `01-store/internal/refusals/refusals.go:115–123`: `Build` пишет `kind`, `error` и поля строки `refusals.tsv`.
- Адаптер двери (`cmd/configstore-tool/adapters.go:33–66`) идёт через тот же `httpd` (`internal/inproc/inproc.go:111–152`) с `Content-Length`. Ответ в inproc тот же.

## Что видела модель
Норма в M. Модель прочитала `01.1-store.norms.md` целиком (вызовы 6–11), `forms/refusals.tsv` (13) и `acceptance/1/README.md` (24). Догадки в `GUESSES.md` нет. Модель сделала по норме: поле `size` необязательное и верное.

## Мнение
Исход — **движок**: норма однозначна, кандидат ей следует. Общий README:333 прямо требует исполнять «special comparison rule» README главы, а движок знает только одну форму фразы. Вторая причина — **норма**: правило `size` написано прозой. В отличие от `error`, у него нет машинной строки. Нет и формы «проверить значение, затем исключить». Модели находка не засчитывается.

Предложение (ворота линии судьи): заглушка отвечает на сц. 22 шаг 1 с `size: 4194364` — ждать GREEN. С `size: "4194364"` и с `size` в сц. 15 — ждать red.

## Вопросы ревьюеру
1. Записать правило `size` фразой той же формы, что `error` (например, «An optional `size` … is checked, then excluded»), чтобы движок брал его из README, а не знал заранее?
2. README.md:19 говорит «for a body refusal», а `README.cases.md` — «only … sc. 22 step 1». Одинаково ли они читаются для прочих отказов `413` (сц. 128 README, чанки без `size`)?

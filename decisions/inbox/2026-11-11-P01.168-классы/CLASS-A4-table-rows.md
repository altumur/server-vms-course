# A4 — строки столбца `tables` маршрута движок не исполняет: `not_executed stand`

**Случаев:** 134 строки:
- P/01.1/door — 97 строк `Platform/common/acceptance/forms/process-1.1.scenarios.tsv` (пробы процесса без D7, P01.149);
- P/01.2/rights — 37 строк `Platform/01-store/vectors/rights-evaluator/expect.tsv` (оценщик прав через сокеты ролей).

## Наблюдение движка
`engine.json`: все строки `not_executed`, `reason: stand`, `response: ""`. Строки заводятся `not_executed stand` при сборке описи (`internal/engine/run.go:160–171`). Дальше их меняют только `run_vectors.go:278` (цели `vector`) и `failRowsForCandidateExit` (`run_stand.go:315–321`, только `puts`/`variants`). Для движков `run` и `l06` строк `tables` не исполняет никто. Кандидат до этих строк не доходил, и исход от него не зависит.

Повтор replay188: строк `process-1.1.scenarios.tsv` и `expect.tsv` в трассе нет. Трасса пишет только опись шагов (`stepInventories`), а строки `tables` в опись строк не входят (`trace/P_01_1_door.jsonl` — 346 записей сценария, `trace/P_01_2_rights.jsonl` — 67). Исполнение строк не повторено, и повторить его этим движком нельзя.

## Норма
- J, `common/acceptance/forms/targets.routing.tsv:5–7`: «tables: JSON array of repository-relative files whose rows the target executes besides the table of its first directory … Each line … is one case of the inventory … the README of the directory of the file says how a row runs»; строки `:12` (`P/01.1/door` — `process-1.1.scenarios.tsv`) и `:15` (`P/01.2/rights` — `expect.tsv`).
- J, `common/acceptance/forms/process-1.1.scenarios.tsv:1–4`: строка — шаг по «A row of scenarios.tsv» общего README, каждый сценарий на своём экземпляре.
- J и M, `01-store/vectors/rights-evaluator/README.md:8–9`: «The runner starts a fresh store with `rights.json` as `{rights}` … and for each row makes a probe through the socket of the role».

## Код кандидата
Не задет. Стенд главы 1.1 и 1.2 у кандидата поднимается (345 и 49 GREEN шагов).

## Что видела модель
Не относится: исход от модели не зависит. Обеих таблиц в M нет (только J). `rights-evaluator/README.md` модель читала (вызов 35).

## Мнение
Исход — **движок**: исполнение строк `tables` не реализовано. GREEN этих целей невозможен ни для какого кандидата. Это предел суда, а не красное кандидата.

Предложение (ворота линии судьи): для каждой цели со столбцом `tables` заглушка с верными ответами должна дать GREEN на строке таблицы, а заглушка с неверным ответом — red.

## Вопросы ревьюеру
1. В P01.127 эти 37 строк rights шли как `not_applicable`, теперь как `not_executed stand`. Разница только в движке (91fe5751 → ef7dcf9b) или в маршруте J?

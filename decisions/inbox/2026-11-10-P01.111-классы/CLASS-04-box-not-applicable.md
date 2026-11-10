# C04. Сборка `box`: групповая цель `blocked` вместо `not_applicable`

**Суть.** Профиль `d9d15b0` объявляет `keys.store_build: box` (`cand/d9d15b0/work/01-store/acceptance.yaml:17`). Раннер даёт групповой цели `not_applicable`. Движок даёт `blocked`, причина `interface:01-store:stand:store-op`.

**Случаев:** одна цель, `P/01.3/group` у `d9d15b0`, 171 шаг. В `summary.json` эти шаги лежат как `red_both`, потому что сравнение по шагам считает `not_applicable` не-GREEN. На уровне цели это расхождение.

## Норма
- `spec/acceptance.norms.md`, P/AC-R007: «`not_applicable` — a key of the profile selects a build for which the target has no meaning, as `keys.store_build: box` for a group stand; the target does not enter the result and is not red».
- `Platform/common/acceptance/README.md:513-517`: «`box` — … the scenarios of the group stand are not_applicable, they do not enter the result and are not red, the lesson is credited without them».
- `README.md:530`: «a scenario with this step [`@group-setup`] the runner plans by `keys.store_build` (above): `raft` — executes it, `box` — not_applicable».

## Наблюдения
- Раннер, `out/d9d15b0/P_01_3_group/runner/report.json`: `"status": "not_applicable"`, `requires` включает `["01-store","keys","store_build"]`.
- Движок, `out/d9d15b0/P_01_3_group/engine.json`: `result blocked`, `reason interface:01-store:stand:store-op`. 171 шаг `not_executed stand`, первый — `07-group-size:5`.

## Код движка
- `internal/engine/verdict.go:65-67`: `notApplicableVerdict()` есть, но вызывается только для ручных шагов (`scenario_verdict.go:92`) и невыбранных строк векторов (`run.go:113`).
- Поиск `store_build` по `internal/` ничего не находит: ключ сборки движок не читает. Проверка интерфейсов (`run.go:150-160`) блокирует цель раньше, чем могла бы применяться норма `box`.

## Мнение представителя
**Движок.** R007 прямо называет случай. Механическое правило: если ключ профиля, указанный нормой, выбирает сборку без смысла для цели (`store_build: box` для группового стенда), итог цели — `not_applicable`. Проверка интерфейсов для такой цели не выполняется.

## Вопросы ревьюеру
1. Как механически взять из J, что `box` делает неприменимым именно групповой стенд, без литерала урока в цикле? Где закрытая запись «ключ → значение → цели `not_applicable`»: README:513-517 (проза) или нужна таблица?

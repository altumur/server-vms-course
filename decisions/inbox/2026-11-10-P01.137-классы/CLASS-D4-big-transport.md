# D4 — `@big(N)` 4 МиБ: движок `red stand transport`

**Случаев:** 1 «раннер GREEN, движок нет» — door `22-body-edge` 1, строка 110. Ворота добавляются в P01.125.

## Суть
Шаг `POST /v1/write {"op":"put","key":"acc/22-body-edge/c1","items":{"blob":"@big(4194304)"}}` с ожиданием `413 {"kind":"toolarge","limit":1048576}`: тело 4 МиБ больше предела 1 МиБ, кандидат должен ответить 413. Цель door идёт через адаптер `door` (`./bin/door-adapter {data}`). Движок: `red`, class `stand`, reason `transport` — запрос не доставлен или ответ не получен. Раннер: `ok: true`.

## Норма
`Platform/common/acceptance/README.md`, строка 250: «`@big(N)` | a substitution in any part of the request: a string of N bytes `x`; inside a JSON string — before serialization …». Предел тела 1048576 и проверка поведения — `Platform/01-store/acceptance/1/README.md:44–48` (класс C8 P01.79). Протокол адаптера двери — `Platform/common/acceptance/PROFILE.md`, «Store door».

## Образцы
| Шаг | Движок (`out/P_01_1_door/engine.json`) | Раннер (`acc/P_01_1_door/P-01.1-door.json`) |
|---|---|---|
| `22-body-edge:110` | `red`, class `stand`, reason `transport` | step 1, line 110, `ok: true` |

## Код движка
`internal/engine/scenario_verdict.go:132–136`:
```go
		case scenarioHTTP:
			observation, ok := c.sendScenarioRequest(parsed)
			if !ok {
				redVerdict(ClassStand, "transport").applyStep(&c.steps[index])
				continue
```
`sendScenarioRequest` (`scenario_verdict.go:~333–356`): при адаптере двери — запрос через `c.adapterDoor` (`run_adapters.go`); отказ передачи даёт `false`. Где именно рвётся передача 4 МиБ (кадр адаптера, буфер чтения, срок) — по отчёту не видно.

## Мнение представителя
Исход — **движок** (предварительно): тот же адаптер кандидата у раннера доставил запрос и получил 413. Главная причина — модель; вторая — **цикл**: заглушка ворот не гоняет через адаптер двери тело размером больше предела. Правило для P01.125 (предлагаемое): заглушка-адаптер принимает кадр с телом `@big(N)` при N больше предела тела и отвечает формой отказа; шаг должен дойти до заглушки целиком (длина тела = N) и получить исход по ожиданию, не `stand transport`.

## Вопросы ревьюеру
1. Не допускает ли протокол адаптера двери (PROFILE.md «Store door») предел кадра, при котором `transport` был бы верным исходом? Если да — это «норма».
2. Подходит ли правило для ворот?

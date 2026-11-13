# X1 — MiniMax 8: у двери нет предела соединений

**Случаев:** цель P/01.1/door, 2 строки сценария `46-overflow` (`process-1.1.scenarios.tsv:100`, `:101`). Третья красная строка того же сценария (`:102`) — класс X2. У Opus 8 сценарий GREEN (`opus8/out/opus8/P_01_1_door/engine.json`).

## Норма
- `forms/daemon-flags.tsv:41` (M): `-max-conns int:1.. 64`, норма P/01.1 N4.
- `spec/01.1-store.norms.md:671` (M): `connection_limit_doors` — соединений больше объявленного предела двери (`-max-conns`), операция не выполнена, 503 с `Retry-After`.
- `spec/01.3-store.norms.md:380` (M): «If the connection limit is exceeded, then the daemon MUST answer 503 `unavailable` with `Retry-After: 1`».
- Правила `@hold` для судьи — `acceptance/1/README.md:41–50` (M).

## Случай (J)
`process-1.1.scenarios.tsv:99–102` (J-вход 5f3c384a): `@hold store 64` → `ok`; затем `GET /v1/get` ждёт `503 {"kind":"unavailable"} @by(1)` и `503 @header Retry-After: =1`. Сценарий J модели не виден: в M нет ни одного `scenarios.tsv` (`M-tree-final/Platform/01-store/forms/`).

## Наблюдение движка
`minimax8/out/minimax8/P_01_1_door/engine.json`, `rows`: строки 100 и 101 — `red implementation`, `status 200 differs`. Шаг `@hold` (строка 99) зелёный: дверь приняла все 64 соединения и обслуживает 65-е.

## Код кандидата
- Флаг разбирается по форме (`internal/daemon/flags.go`, форма вшита `//go:embed forms/daemon-flags.tsv`). Мутация типа `-max-conns` даёт ожидаемый отказ (`minimax8/form-mutation/report.md`, строка `-max-conns`, «ровно так»).
- Значение флага нигде не читается: поиск `max-conns|MaxConns|Retry-After` по `01-store/**/*.go` пуст. Цикл приёма `internal/daemon/http_server.go:52–61` на каждое соединение запускает `go s.serveConnection(...)` без счётчика.
- Собственного теста предела нет.

## Код движка
`runner/directive.go:68`, `:284–315` (снимок 340fbb39) — `@hold`; движок прав: у Opus 8 тот же шаг GREEN.

## Что видела модель
- `-max-conns` в голове этапа `launch` (`stages.tsv:25`, `forms/daemon-flags.tsv`), N4 главы 1.1 — в голове этапа `http` (`stages.tsv:28`).
- Ворота этих этапов — `mech` (сборка, vet, свои тесты, трассировка пунктов, проба профиля): `passport.json`, `stages.http.gate = "mech"`; `log.jsonl`, `judge.passed = 0, total = 0` во всех раундах. Сценарии стенда не исполнялись (P01.309, «Б1»).
- Пункт чек-листа о пределе соединений — внутри P/01.3-01 (`spec/01.3-store.norms.md:810`, «the [probe] `01-connections`»), он приписан этапу `group` и не закрыт.
- Догадки нет (`GUESSES.md`, 3 записи, ни одна не о пределах).

## Мнение окна
Исход — **кандидат**. Норма однозначна и стоит в головах двух этапов. Причина по доп. (44): **модель (без обратной связи)**. Вторая — **цикл**: обязанность без пункта чек-листа своего этапа воротами `mech` не видна.

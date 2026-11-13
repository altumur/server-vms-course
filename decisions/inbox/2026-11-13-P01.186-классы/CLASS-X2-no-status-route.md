# X2 — MiniMax 8: у демона нет `/v1/status` (и служебных дверей вообще)

**Случаев:** P/01.1/door, 1 строка — `process-1.1.scenarios.tsv:102` (`admin GET /v1/status` → ждёт 200, получено 404). Скрытый объём больше: P/01.3/daemon заблокирован неполным профилем (X5), его сценарии `15-service-doors`, `16-status-no-api`, `04-store-metrics` не исполнялись.

## Норма
- `spec/01.3-store.norms.md:24` (M): `status` — ответ `/v1/status`, формы `forms/status-fields.tsv`, `spec/01-store.api.openapi.yaml`.
- `stages.tsv:31` (M): этап `daemon_doors` — «The daemon on one box: status, the service doors, the metrics, the id memory»; ворота `accept:1.3:04-store-metrics,15-service-doors,16-status-no-api,...`.

## Наблюдение движка
`minimax8/out/minimax8/P_01_1_door/engine.json`, `rows`, строка 102: `red implementation`, `status 404 differs`, тело 54 байта (отказ «нет маршрута»).

## Код кандидата
`internal/daemon/handler.go:158–208`: маршруты только `/v1/get`, `/v1/list`, `/v1/write`, `/v1/rights`, `/v1/copy`; остальное — `noRouteResponse()`. Нет `/v1/status`, `/metrics`, `/v1/join`, `/v1/leave`. Модель отметила отсутствие маршрута статуса только для группы: `NOTES.md:104` («no ... status/metrics route»); для одного узла пропуск не записан.

## Что видела модель
- Раунд 11–12 — этап `daemon_doors`. Модель читала OpenAPI и формы статуса (`round-012.json`, сообщения 36–66) и в последнем ходе раунда написала: «The core service-door behavior can now be implemented independently» (`round-012.json`, сообщение 72). Раунд кончился по окну (`round-012.json`, `info.window_stop`: 149 102 + 32 000 ≥ 180 000).
- В том же раунде ворота `mech` стали зелёными, 42/42 (`passport.json`, `stages.daemon_doors.gates`), и цикл закрыл этап. Красным в раунде 11 был только пункт P/01.1-11 (`norm_trace`, раунд 11, `red: ["P/01.1-11"]`). Это единственный пункт чек-листа этапа (`stages.tsv:31`); статус в нём не участвует.
- Следующие раунды шли по этапам `daemon_copy`, `durable`, `group`; к статусу модель не вернулась. Головы этих этапов о пропуске не говорили.
- Догадки нет.

## Мнение окна
Исход — **кандидат** (маршрута нет). Причина по доп. (44): **цикл** — этап закрыт механическими воротами посреди работы над его главным поведением, а ворота `mech` статус не проверяют. Вторая — **модель (без обратной связи)**: план этапа она знала (`DESIGN.md:190–192`, `PLAN.md:99`). Третья — **спека**: у этапа `daemon_doors` в `stages.tsv:31` нет пункта чек-листа про статус и служебные двери (они внутри P/01.3-01 этапа `group`), поэтому трассировке нечего требовать на этом этапе.

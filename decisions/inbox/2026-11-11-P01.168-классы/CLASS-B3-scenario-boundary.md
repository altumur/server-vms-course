# B3 — движок не сбрасывает стор между сценариями: шаг сц. 23 судится на состоянии сц. 08

**Случаев:** 1 red класса `implementation`, `expectation` — сц. 23-service-door-forms стр. 209 (шаг 6) цели P/01.3/daemon:
`admin POST /v1/write {"op": "floor", "floor": 4294967296, "id": "f2"}` → ждёт `200 {"index": "@any"}`.

## Наблюдение движка
`engine.json`: стр. 209 — `red`, `class: implementation`, `reason: expectation`; стр. 204–208 того же сценария GREEN.

**Повтор replay188** (`replay188/trace/P_01_3_daemon.jsonl`; итог совпал с диагностикой):

| Таблица:строка | Отправлено движком | Статус | Тело |
|---|---|---|---|
| `acceptance/3/scenarios.tsv:28` (сц. 08, шаг 6) | `admin POST /v1/write {"op": "floor", "floor": 4294967296, "id": "f2"}` | 409 | `{"kind":"refused","error":"the floor is not higher than the current one"}` (ожидание стр. 28 — 409, GREEN) |
| `:34` (сц. 08, шаг 12) | `… {"op": "floor", "floor": 9007194959773696, "id": "f7"}` | 200 | `{"index":"2"}` |
| `:35` (сц. 08, шаг 13) | `admin GET /v1/get?key=platform/epoch_floor` | 200 | `{"items":{"floor":"9007194959773696","generation_at":"1794402496.149"},"index":"2"}` |
| `:209` (сц. 23, шаг 6) | `admin POST /v1/write {"op": "floor", "floor": 4294967296, "id": "f2"}` | 409 | `{"kind":"refused","error":"the floor is not higher than the current one"}` |

Общий стор на все сценарии виден и по версиям: 1 и 2 (сц. 08, стр. 23, 34), 3 (сц. 14, стр. 81), 4 (сц. 19, стр. 177), 9 (сц. 21, стр. 193), 11 и 12 (сц. 30, стр. 267, 272). На свежем сторе каждого сценария первая запись имела бы небольшую версию заново.

Код движка `ef7dcf9`, `internal/engine/scenario_verdict.go:54–99` (`executeScenarioSteps`):
- стор стенда поднимается один раз на цель (`:58–66`, `waitForStoreReady`);
- при смене сценария (`:87–95`) сбрасываются только переменные (`bindings`), роль и признак обрыва. Процессы не останавливаются, `{data}` не очищается, память повторов не стирается.

Перед сц. 23 на том же сторе прошёл сц. 08-floor-replay. Его шаги поднимают пол до `9007194959773696` (стр. 34, GREEN; стр. 35 читает его, GREEN), а `id: f2` с полом `4294967296` уже получил 409 (стр. 28, GREEN).

Повтор подтвердил: кандидат на стр. 209 отвечает 409 `refused`. Почему — по коду:
- `internal/storecore/apply.go:212–222` (`applyFloor`): сначала память id (`s.replay(f.ID, fp)`, `:217`) — у `f2` с тем же телом сохранён отказ сц. 08;
- затем «только вверх»: `f.Floor <= cur` → `FloorNotHigherID` (`:220–222`).

На свежем сторе тот же код дал бы 200: пола нет, `cur = 0`. Это **по чтению кода, не повторено** (повтор шёл тем же движком, без сброса).

## Норма
J-вход `49e62279`:
- `Platform/01-store/acceptance/3/README.md:110–112`, «Scenario boundaries»: «Between scenarios the runner stops the processes, resets the store and the variables; the group members and their directories too»;
- там же `:116`: «Before each automatic scenario stop the processes of the previous one, create separate empty row/object stores and clear the variables/replay memory»;
- `common/acceptance/README.md:187`: «Instance — per scenario (P/01.1) or per full run, as the lesson README says»;
- M, `01-store/spec/01.3-store.norms.md:306`: «a new id with floor ≤ the current one — 409 refused»; «A replay of floor with the same id returns the saved outcome».

Ожидание стр. 209 (200) верно только на свежем сторе. Сценарий написан под границу `:112`.

## Код кандидата
`internal/storecore/apply.go:212–228`; профиль `01-store/acceptance.yaml:8` (`stand.store`, `-dir {data}/configstore`). По норме 01.3:306 кандидат прав на общем состоянии: ответ 409 подтверждён повтором. На свежем сторе, по чтению кода, был бы 200 с новой версией.

## Что видела модель
Норма пола (01.3:306) — в M. Модель прочла 01.3 целиком (вызовы 17–21) и `acceptance/3/README.md` с «Scenario boundaries» (вызов 33). На поведение кандидата класс не влияет. Догадок нет.

## Мнение
Исход — **движок**. Норма однозначна: `3/README.md:112`, `:116`. Главная причина — модель линии судьи. Вторая — **цикл**: ворота не подавали два сценария, второй из которых зависит от чистого стора. Последствие шире одного шага: все сценарии цели судятся на накопленном состоянии. Их GREEN зависит от порядка и может быть ложным в обе стороны. Так и вышло с шагами после неисполненного `@restart` (B1).

Предложение для ворот: заглушка-стор, которая помнит состояние между сценариями, на паре «сц. A пишет, сц. B читает отсутствие» должна быть red, а верный движок, поднимающий свежий стор на каждый сценарий, — GREEN.

## Вопросы ревьюеру
1. Нужна ли в P/AC (не только в README урока) норма о границе сценария для целей `run`/`l11`? Сейчас это `3/README.md:112`, `:116` и общий `README.md:187` с отсылкой к уроку.
2. Нужен ли отдельный повтор сц. 23 на свежем сторе (движком со сбросом или одним сценарием), или достаточно повтора 409 и чтения `apply.go:212–222`?

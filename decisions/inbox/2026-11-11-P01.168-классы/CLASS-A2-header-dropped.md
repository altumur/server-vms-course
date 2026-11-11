# A2 — движок разбирает `@header`, но не отправляет заголовок: шаги проверки заголовка роли — red

**Случаев:** 2. P/01.2/rights, `Platform/01-store/acceptance/2/scenarios.tsv`:
- `:21` — `08-role-header` шаг 2: `@as testsubworker @header X-Configstore-Role: console POST /v1/write {bad`, ожидание `403`;
- `:33` — `12-list-role-header` шаг 2: `@as testsubworker @header X-Configstore-Role: console GET /v1/list?prefix=testsub/`, ожидание `403`.

`:20` (`08-role-header` шаг 1, тело в форме) — GREEN, но случайно, см. ниже.

## Наблюдение движка
`engine.json`: `red`, `implementation`, `expectation`.

`parseScenarioRequest` (`internal/engine/scenario_verdict.go:185–189`) на `@header` пропускает три поля (`fields = fields[3:]`) и не сохраняет их. В `scenarioRequest` поля заголовков нет. `sendUnixHTTPObservation` (`:423–440`) пишет только `Host`, `Connection`, `Content-Type`, `Content-Length`. Других мест с `@header` в `internal/engine` нет.

**Повтор replay188** (`/home/pilot/owner-receipts/P01.188-court-claude-20261111/replay188/``trace/P_01_2_rights.jsonl`). В трассе `request_sent` — текст строки после подстановок, до разбора директив, а не байты на проводе. Что заголовок не ушёл, видно по ответам: с заголовком кандидат отказывает до разбора тела (`door.go:130–137`).

| Строка | Запрос (текст строки) | Статус | Тело | Итог |
|---|---|---|---|---|
| `:20` | `@as testsubworker @header X-Configstore-Role: console POST /v1/write {"id":"b9",…"testsub/counters/c8"…}` | 403 | `{"kind":"forbidden","error":"testsubworker may not write testsub/counters/c8"}` | GREEN |
| `:21` | `… @header X-Configstore-Role: console POST /v1/write {bad` | 400 | `{"kind":"badrequest","error":"the body is not JSON by RFC 8259"}` | red |
| `:33` | `… @header X-Configstore-Role: console GET /v1/list?prefix=testsub/` | 200 | `{"keys":{"testsub/epoch/":"2",…}}` | red |

`:20` зелёный не по заголовку: отказ — `rights` («may not write»), а не `role_header`. У `testsubworker` нет права записи в `testsub/counters/*` (`acceptance/2/inputs/rights.json`). Ответ кандидата с заголовком напрямую не повторён: проверено только то, что ответы совпадают с запросом без заголовка.

## Норма
- J и M, `common/acceptance/README.md:275`: «`@header <Name>: <value>` before the method | add a header to one request».
- M, `01-store/spec/01.2-store.norms.md:161–163` (N3 check, шаг 1): «If a header with a role is on a role socket, return `403` before the body is parsed (a body out of form with such a header is also `403` …)»; `:193`: «The forwarding conditions apply to list and to /v1/rights too».
- `forms/refusals.tsv:35`: `role_header … 403 forbidden`.

## Код кандидата
`01-store/internal/door/door.go:106–137`: `storeRoute` до разбора тела зовёт `identity`. На ролевом сокете любой `X-Configstore-Role` даёт `role_header` 403, то же для `/v1/list`. Имя заголовка — в профиле (`keys.role_header: X-Configstore-Role`). Собственный тест модели — `internal/inproc/door_test.go:212–218` (`TestRoleHeaderAndAdmin`: «role header», «role header before the body»).

## Что видела модель
Норма в M. Модель прочитала `01.2-store.norms.md` целиком (вызов 16) и `acceptance/2/README.md` (34). Догадки нет. Модель сделала по норме и закрепила это тестом.

## Мнение
Исход — **движок**: директива словаря не исполняется. Повтор это подтвердил: тексты ошибок — ответы роли без заголовка. Шаг 1 сц. 08 зелёный по чужой причине (`rights`, а не `role_header`), это ложный GREEN. Модели находка не засчитывается.

Предложение (ворота линии судьи): заглушка отвечает `403` только при заголовке `X-Configstore-Role` и `200/400` без него. Шаги `:20`, `:21`, `:33` должны дать GREEN только с заголовком.

## Вопросы ревьюеру
1. Сц. 08 шаг 1 даёт 403 и без заголовка (нет права записи). Сменить ключ на `testsub/slots/…`, чтобы шаг проверял заголовок, а не права?

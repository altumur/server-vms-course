# Данные случаев только для судьи

Этот русский текст — производный от `acceptance/6/README.cases.md`, руками не правится (ADR-0121).

Общие правила остаются в [README.md](README.md). Следующие исходные отрывки сохраняют прежние связи именованных случаев как материал только для судьи.

<!-- original-mixed-case-paragraph -->

Норма главы — [`06.6-console.norms.md`](../../spec/06.6-console.norms.md) N5. Сценарии перенесены из приёмок
M10/04 (01–07),
M10/10 (01 → 08, 02 → 10, 09, 12) и
M10/11 (03 → 11) (стадия B, ADR-0083 доп. (1): без
изменения поведения); номера и шаги — прежние, кроме совпавших номеров: `08-schema` (в M10/10 — `01-schema`; номер 01
занят `01-unplaced` из M10/04), `10-drain-strand` (в M10/10 — `02-drain-strand`; 02 занят `02-unplaceable`),
`11-schema-processes` (в M10/11 — `03-schema-processes`; 03 занят `03-policy`). 17 сценариев / 195 шагов (сц. 17 — версии снимков настроек, ADR-0094 B4; сц. 13–16 — второй проход аудита покрытия P/06, Gemini; сц. 01, 08, 10, 12 — первый шаг `@start resource` по C06-PULSE-LAPSE-503-03, решение «Архитектора» 2026-10-29; сц. 09 — первый шаг `@start resource`: консоль и контроллер читают пульс воркера дверью объектов ресурса своего сервера, без ресурса «не известно», [договор клиента хранилища объектов](../../../../common/ru/contracts/object-client.md) `door`; P03-OBJECTS-DEFAULT-1FD; решение «Архитектора» 2026-10-27; шаг 04/14 и 05/6 — решение «Архитектора» 2026-10-20, разбор ревью стадии B 6–7; шаг 05/5 — разбор ревью стадии B 6–7, № 40; сц. 12: шаги 9–10,
13–14, 17–18 добавлены — разбор ревью стадии B 6–7, № 21).

<!-- original-mixed-case-paragraph -->

`@spoil object`, `@until`, `@sleep` (сц. 13), `@big(N)`; ожидание — точный код или `2xx`/`4xx` и подмножество полей. Запрос без префикса
двери (сц. 01–07, бывшая приёмка M10/04) идёт в консоль `testsub` — дверь урока P/06; `Idempotency-Key` — по словарю,

<!-- original-mixed-case-paragraph -->

## Сц. 01–07: один экземпляр без воркеров

<!-- original-mixed-case-paragraph -->

Сценарии выполняются последовательно на одном экземпляре: 02 использует u1 из 01, 07 — u1 из 01. Между ними состояние не

<!-- original-mixed-case-paragraph -->

placement.servers имеет эффективное умолчание shared (ключ в testsub не задан). Работает её контроллер и ресурс `srv-a` — первым шагом сц. 01 (`@start resource`: пульсы консоль читает дверью объектов

<!-- original-mixed-case-paragraph -->

Между 01 и 02 контроллер должен завершить хотя бы один проход после создания u1.

<!-- original-mixed-case-paragraph -->

## Сц. 08–16: свежий стенд на сценарий

<!-- original-mixed-case-paragraph -->

схемой 1 (сц. 08 ждёт `understood: 1`, сц. 11 — `understood: 1`, `can_raise_to: 1`); предел тела консоли — 1 МиБ.

<!-- original-mixed-case-paragraph -->

ролей»): шаг 14 сц. 04 и шаг 10 сц. 05 читают `platform/drain` и `platform/servers/srv-a` вне префикса подсистемы; `@as <роль>` — сокет роли до конца сценария.

<!-- original-mixed-case-paragraph -->

## Аудит покрытия P/06, второй проход (Gemini)

Сц. 13–16 (`audit-coverage-gemini` 0a5ae79f9) — стенд сц. 08–12: свежий на сценарий, ресурс `srv-a` первым шагом, без
контроллера и воркеров. Строки мимо писателя — дверью хранилища ролью владельца: слот — `testsubworker` (как сц. 07, 09),
строки консоли (`testsub/policy`, `platform/drain`, `platform/schema`, `platform/servers/srv-a`) — `console`.


<!-- original-mixed-case-paragraph -->

Пульсы воркера `w-1` для `@put object` (команда записи объекта «Стенда», мимо писателя): `hb-w-1-no-status.json` (сц. 07,
09; из приёмок M10/04 и M10/10 — байты совпадают), `hb-w-1-pending-0.json`, `hb-w-1-pending-missing.json`,
`hb-w-1-pending-fraction.json`, `hb-w-1-pending-minus-zero.json`, `hb-w-1-pending-2p63.json`, `hb-w-1-schema-fraction.json`,
`hb-w-1-build-number.json` (сц. 12; из приёмки M10/10, строка реестра e31e5c28).

<!-- original-mixed-case-paragraph -->

Сц. 01–07 — один экземпляр, состояние между ними не сбрасывается. Перед сц. 08–16 раннер останавливает процессы,

<!-- original-mixed-case-paragraph -->

## Сц. 17: версии снимков настроек (ADR-0094 B4)

<!-- original-mixed-case-paragraph -->

Свежий стенд, ресурс `srv-a` первым шагом; строк `testsub/policy`, `platform/drain`, `platform/servers/srv-a`, `platform/schema` до сценария нет. Шаг 25 ждёт, пока сервер станет известен, поэтому `@until`.

# D6 — шаг после красного шага: inproc `40-batch-rights:349` GREEN только у движка

**Случаев:** 1 «движок GREEN, раннер нет».

## Суть
Сценарий `40-batch-rights` в `Platform/01-store/acceptance/1/scenarios.tsv`:
- шаг 3, строка 343: `POST /v1/write {"op":"batch","writes":[{"op":"put","key":"acc/40-batch-rights/a",…}],"guards":[{"key":"other/40-batch-rights/x","index":""}]}`, ожидание `403 {"kind":"forbidden"}` — красный у обоих (кандидат);
- шаг 9, строка 349: `GET /v1/list?prefix=other/40-batch-rights/`, ожидание `200 {"keys":{}}` — у раннера red (тело 187 Б), у движка GREEN.

Оба судьи после красного шага 3 сценарий продолжают; к шагу 9 у них, судя по исходу, разное состояние хранилища (у раннера под `other/` есть ключи, у движка — нет).

## Норма
`Platform/common/acceptance/spec/acceptance.norms.md:135`: «A failed step ends its scenario only when it is a directive of preparation without which the later steps have no meaning: `@spoil row`, …» — обычный красный шаг сценарий не прерывает. Роль сценария — README урока (`Platform/01-store/acceptance/1/README.md`), двери — `Platform/common/acceptance/README.md:234–245`.

## Образцы
| Шаг | Движок (`out/P_01_1_inproc/engine.json`) | Раннер (`acc/P_01_1_inproc/P-01.1-inproc.json`) |
|---|---|---|
| `40-batch-rights:343` | `red implementation`, reason `expectation` | step 3, `ok: false`, тела 25, 18, 164 Б (тела опущены, sha256 в отчёте) |
| `40-batch-rights:349` | `GREEN` | step 9, `ok: false`, тела 187 и 52 Б (sha256 `99542851…`, `d20e317e…`) |

## Код движка
`internal/engine/scenario_verdict.go:62–130` — цикл шагов: `aborted` ставится только для `abortingDirective` (строки 124–130), обычный красный шаг сценарий не прерывает — по норме 135. Отличие состояния к шагу 9 — от того, какие шаги 4–8 и с какой ролью исполнил каждый судья; по отчётам без тел ответов это не установить.

## Мнение представителя
Исход — **не решено**. Возможны: (а) один из судей исполнил шаги 4–8 иначе (роль, связи, подстановки) — тогда виновник он; (б) кандидат недетерминирован между прогонами. Механического правила пока не предлагаю.

## Вопросы ревьюеру
1. По сырым выходам (у раннера — `…-processes/case-*`, у движка тел нет) можно ли установить, какие запросы шагов 4–8 ушли у каждого?
2. Если нельзя — нужна ли норма о том, что отчёт судьи несёт тела (или их хэши) ответов, чтобы такие расхождения разбирались? Это была бы правка P/AC (отчёт), не движка.

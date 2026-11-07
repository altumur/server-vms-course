# Договор слота: состояния строки слота и сроки

Текст производный от `contracts/slot.md`, руками не правится: источник — английский [`contracts/slot.md`](../../contracts/slot.md), правка идёт в него, русский пересобирается переводом (ADR-0121; ADR-0124 доп. (1) п. 4).

Общий договор модуля «Платформа» (ADR-0083 доп. (5), доп. (13): состояние строки слота судят воркер, контроллер, консоль и
агент — договор, а не копии в главах; аудит раскладки A-04, решение «Архитектора» 2026-10-25). Владелец — глава
[P/03.2](../../../03-worker/ru/spec/03.2-worker.norms.md) N1.4 (строка `<sub>/slots/<name>`). Участники: воркер — захват и
продление (P/03.2 N3); контроллер — судья слота, уход единиц, заказ ([P/04](../../../04-controller/ru/spec/04-controller.norms.md)
N1.4, N3); консоль — `WorkerRow.released`, `slot_taking`, `slot_until`, `slot_garbled` ([P/06.5](../../../06-console/ru/spec/06.5-console.norms.md)
N2, N3 «/servers»), дренаж ([P/06.6](../../../06-console/ru/spec/06.6-console.norms.md)); агент — живость воркера на домене
([P/09.1](../../../09-agent/ru/spec/09.1-agent.norms.md) N1.4); пул — [договор пула](pool.md) «Живой воркер».

Перенесено из P/03.2 N1.4 (`states`, `SLOT_TERM`, `TORN_STILL`) без изменения поведения; P/03.2 и читатели — ссылкой
сюда. Форма строки, имя и порядок имён — у владельца и в [договоре имени слота](slot-name.md); возраст наблюдаемой версии —
[договор наблюдения](observation.md) «Наблюдение версии».

Нормативные слова — по [канону курса](../NORMATIVE-TERMS.md).

## Форма

Строка `<sub>/slots/<name>` — семья `slots`: форма `Platform/03-worker/data/slots.schema.json`, исходы
`Platform/03-worker/data/slots.outcomes.tsv` ([форма](../../../03-worker/data/slots.schema.json),
[исходы](../../../03-worker/data/slots.outcomes.tsv)); поля `holder`, `until`, `released`, `gen`, `server` — там и в P/03.2
N1.4.

## Состояния

```yaml
states:
  held:      читаемый слот, holder ≠ "", released = false, gen ≥ 1, возраст наблюдаемой версии < SLOT_TERM
  lapsed:    те же поля, возраст наблюдаемой версии ≥ SLOT_TERM; само по себе не разрешает захват
  released:  released = true
  taking:    released = taking — захват в работе: для всех читателей не жив (как released), для захвата — свободный
             (как released: захватчик мог умереть между записями); контроллер уводит его единицы только после SLOT_TERM
             неизменной версии (P/04 N3 «уходит»); всякое «released» ниже без значения — released ≠ false;
             читаемая строка без поля released — как released ≠ false (не held; для захвата — как released), без
             поля holder — как holder = "" (разбор ревью стадии B 3–5, № 6)
  torn:      строка не читается: until не число или не конечно, gen не точное десятичное целое в 1..9007199254740991;
             конечный until в прошлом/будущем относительно судьи не делает строку порванной
```

## Сроки

```yaml
SLOT_TERM: 45          # срок слота, с
TORN_MARGIN: 5         # с; самостоятельный запас наблюдения порванной строки, не HOLD_SKEW
TORN_STILL: SLOT_TERM + TORN_MARGIN  # неизменное наблюдение до переписывания порванной строки с читаемым gen
```

## Векторы

Пакет [`slot`](../vectors/slot/README.md): суждение judge(row, age) → `held`, `lapsed`, `released`, `taking`, `torn` (с
`takeable`) — по строке на состояние, границы `SLOT_TERM` и `TORN_STILL`, `until` сверх binary64 (C140-SLOT-TIME-01). Граница
свежести пульса — пакет [`fresh-age`](../vectors/fresh-age/README.md) договора наблюдения; переходы — сценарии приёмки P/03.2,
P/04 и чтение.


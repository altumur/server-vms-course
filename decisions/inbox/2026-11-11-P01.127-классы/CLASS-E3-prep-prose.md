# E3 — подготовка сц. 21 записана прозой: строки `other/21-rights/c9` нет, шаг 6 красный

**Случаев:** 1 — `P/01.1/inproc`, `acceptance/1/scenarios.tsv:107` (21-rights:6): `GET /v1/list?prefix=other/21-rights/` → ожидание `200 {"keys":{"other/21-rights/c9":"$v"}}`. Движок: `red implementation expectation`. Повтор: `200 {"keys":{}}`.

## Норма
J: `Platform/01-store/acceptance/1/README.cases.md:105–107` («Original passage 15»): «before its first step the runner in the preparation (not a checked request) writes the row `other/21-rights/c9` `{n: "1"}` through `admin.sock` of the instance (`{socket}` of «Stand»); step 6 sees its name and version without the value». В `scenarios.tsv` и `seams.tsv` этой подготовки нет: ни директивы, ни строки `admin`.

## Код движка
Поиск `c9`, `21-rights`, `README.cases` по `engine/internal/engine/*.go` — 0 совпадений: движок исполняет только таблицы, прозу подготовки не читает.

## Кандидат
Не причастен: строку записывает стенд до сценария. Без неё листинг пуст — так и должно быть.

## Мнение представителя
Исход — **норма**: подготовка, от которой зависит шаг, записана только прозой. По P/AC-R002 и lesson-spec «Готовность к варианту Б» п. 4 проверяемое должно быть данными закрытого словаря. Вторым — **движок**: шаг, зависящий от неисполненной подготовки, по норме не red `implementation`. Он `not_executed` с причиной (R030) или вне описи как «проза без машинной формы».

Правка спеки: подготовка — директивой в `scenarios.tsv` сц. 21 (шаг `admin POST /v1/write {"op":"put","key":"other/21-rights/c9",…}` с пометкой «не проверяемый запрос», если словарь такую даёт, или `@setup`).

## Вопросы ревьюеру
1. Есть ли в словаре общей приёмки форма «подготовка через `admin`, не проверяемый шаг»? Если нет — это пробел словаря, а не только сц. 21.
2. Есть ли ещё подготовки прозой в README.cases.md глав 1–3 (поиск «before its first step», «in the preparation»)?

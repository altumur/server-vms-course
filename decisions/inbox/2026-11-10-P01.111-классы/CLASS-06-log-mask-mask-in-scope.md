# C06. log-mask `mask_in.tsv`: движок судит таблицу, не назначенную `01-store`

**Суть.** На `P/01/vectors-log-mask` у `c36e6ac` движок судит 33 строки `mask_in.tsv`, 30 из них GREEN. Раннер эту таблицу для `01-store` не судит. В RESULT-P01.80 это записано как недостаток раннера, но по назначению потребителей прав раннер.

**Случаев:** 30 (`engine_GREEN_runner_not|GREEN|None|absent`).

## Норма
- `Platform/common/vectors/consumers.tsv:137`: `common/log-mask	mask_in.tsv	06-console	…`. Строки 128-136: `cases.tsv` — для `01-store` … `10-domain-console`. `mask_in.tsv` назначена только `06-console`.
- `common/vectors/wire.tsv:64`: строка `mask_in.tsv` есть в форме протокола (входы `value`, `expect` из столбца `expect`). Форма описывает таблицу, но не назначает её владельцу.
- `common/acceptance/README.md:344-348`: «Vectors and scenarios remain judge-only»; назначение таблиц — по `consumers.tsv`.

## Наблюдения
- Движок, `out/c36e6ac/P_01_vectors-log-mask/engine.json`: строки `mask_in.tsv` 5 (`four-stars`), 16 (`dot-operator`), 20 (`mixed-set`) — `GREEN`, `response valid`.
- Раннер, `…/runner/P-01-vectors-log-mask.txt`: «01-store vector-log-mask 30/39; NOT GREEN». 39 — это только `cases.tsv`.

## Код
- Раннер, `runner/c_resource_vectors.py:160-161`: `if driver == 'vector-log-mask' and name == 'mask_in.tsv' and owner != '06-console': continue`. Пропуск по назначению потребителя.
- Движок отбирает строки по `wire.tsv` и маршруту цели. Фильтра по `consumers.tsv` для таблицы в коде вектора не видно. Точное место пусть подтвердит ревьюер: `internal/engine/run_vectors.go`, отбор строк описи.

## Мнение представителя
**Движок.** По `consumers.tsv` цель `01-store` не потребитель `mask_in.tsv`. Строки этой таблицы для `01-store` должны быть невыбранными (`not_applicable`) или отсутствовать в описи, но не исполняться. Механическое правило: опись векторной цели включает только таблицы, где `consumers.tsv` называет владельца цели.

## Вопросы ревьюеру
1. Достаточно ли `consumers.tsv` как нормы назначения, если `wire.tsv` перечисляет таблицу пакета без владельца? Или здесь пробел: `wire.tsv` и маршрут цели `["…/log-mask","…/secret-in"]` не говорят, какие таблицы пакета судит цель?

# Консоль кластера — урок P/06

Микромодуль: процесс console. Что нормирует и откуда — [записка модуля](../module-design.md), таблица «Уроки».

Раскладка каталога (после переноса, стадия B). Глава 6.7 — поздний слой консоли кластера — написана переносом уроков
8–10 (разбор ревью стадии A 6–7, № 27; разбор ревью стадии B 8–10, № 22: М-15). Договора библиотеки у консоли нет — это процесс с HTTP-дверью:

```text
06-console.md                        лекция
spec/06.1-console.norms.md           нормы главы 6.1 — дверь единиц: строки, тела, таблицы
spec/06.2-console.norms.md           нормы главы 6.2 — запись секретов
spec/06.3-console.norms.md           нормы главы 6.3 — сторожевая и люди
spec/06.4-console.norms.md           нормы главы 6.4 — просьбы и события
spec/06.5-console.norms.md           нормы главы 6.5 — наблюдения
spec/06.6-console.norms.md           нормы главы 6.6 — двери управления
spec/06.7-console.norms.md           нормы главы 6.7 — поздний слой: книга члена, пересылка к домену, двери переноса
spec/06-console.api.openapi.yaml     двери (один контракт урока)
spec/06-console.README.md            инструкция реализации
lifecycle.md                         флаги, окружение, коды выхода, юниты
data/<семья>.schema.json, .outcomes.tsv схемы семей (JSON Schema, ADR-0092; ADR-0088): next-id, sweep (6.1); requests, asked,
                                     commands (6.4); door-signer, door-keys (6.5); policy, server-labels, drain,
                                     decommission, schema (6.6)
vectors/<алгоритм>/                  векторы: fault, values-by-type (6.1); secret-in, log-mask (6.2, в common/vectors); rid, requests-body,
                                     request-digest (6.4); resolve (6.7)
acceptance/1/ … acceptance/7/        приёмка глав 6.1–6.7 (README, scenarios.tsv, corrections.tsv; 2/fields.yaml,
                                     5/inputs/, 5/probe-x.subsystem.yaml, 6/inputs/)
```

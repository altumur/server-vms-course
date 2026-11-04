# Консоль кластера — урок P/06

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

Микромодуль: процесс console. Что нормирует и откуда — записка модуля `Platform/module-design.md` (для человека, в выгрузку не входит), таблица «Уроки».

Раскладка каталога (ADR-0124: английский источник — на каноническом пути, русский текст для человека — в `ru/`). Глава 6.7 — поздний слой консоли кластера — написана переносом уроков
8–10 (разбор ревью стадии A 6–7, № 27; разбор ревью стадии B 8–10, № 22: М-15). Договора библиотеки у консоли нет — это процесс с HTTP-дверью:

```text
README.md                            этот файл
spec/06.1-console.norms.md           нормы главы 6.1 — дверь единиц: строки, тела, таблицы
spec/06.2-console.norms.md           нормы главы 6.2 — запись секретов
spec/06.3-console.norms.md           нормы главы 6.3 — сторожевая и люди
spec/06.4-console.norms.md           нормы главы 6.4 — просьбы и события
spec/06.5-console.norms.md           нормы главы 6.5 — наблюдения
spec/06.6-console.norms.md           нормы главы 6.6 — двери управления
spec/06.7-console.norms.md           нормы главы 6.7 — поздний слой: книга члена, пересылка к домену, двери переноса
spec/06.8-console.norms.md           нормы главы 6.8 — папки кластера (ADR-0096)
spec/06.9-console.norms.md           нормы главы 6.9 — групповые операции (ADR-0095)
spec/06-console.api.openapi.yaml     двери (один контракт урока)
spec/06-console.README.md            инструкция реализации
lifecycle.md                         флаги, окружение, коды выхода, юниты
data/<семья>.schema.json, .layers.tsv, .outcomes.tsv семьи данных (JSON Schema, ADR-0092; ADR-0088): next-id, sweep (6.1); requests, asked,
                                     commands (6.4); door-signer, door-keys (6.5); policy, server-labels, drain,
                                     decommission, schema (6.6); folders, memberof, memberof-gone (6.8); operations, operations-epoch,
                                     operations-turn, opsteps, opbusy, opcount, opdone (6.9)
data/refusal-words.tsv               закрытый перечень слов error по дверям (6.1, 6.4, 6.5, 6.8, 6.9; ADR-0094 B5)
vectors/<алгоритм>/                  векторы: rid, requests-body, request-digest, reap (6.4); contender-projection, metrics (6.5);
                                     resolve, key-families (6.7); op-step (6.9); fault, values-by-type (6.1) и secret-in, log-mask (6.2) — в common/vectors
acceptance/1/ … acceptance/9/        приёмка глав 6.1–6.9 (README.md, scenarios.tsv; 5/inputs/, 5/probe-w.subsystem.yaml,
                                     5/probe-x.subsystem.yaml, 6/inputs/)
journal/corrections-<K>.tsv          журнал исправлений ИИ главы K (1–9) — история, не вход; в выгрузку не входит
ru/                                  для человека, в выгрузку не входит — лекция ru/06-console.md, переводы английского текста тем же путём
```

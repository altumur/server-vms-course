# М10 Платформа: хранилище и спека

Все одиннадцать уроков в main (2026-10-14, «Архитектор» за «Спецификацию»). В уроках 1–5 лекция отделена от норм: она лежит в каталоге модуля, нормы, OpenAPI и инструкция реализации — в общем `spec/` с префиксом лекции (ADR-0080, решение владельца 2026-10-15). У урока 5 нет собственной HTTP-двери: в spec/ только нормы и инструкция (ADR-0082 доп. 13). В уроках 6–11 повествование и нормативные разделы пока находятся в одном файле. Реализации — Python курса (`Source/`), Go продукта, позже C++ прошивки — проверяются приёмкой из `Source/tests/testdata/acceptance/М10_Platform/`. Нарезка, форма урока и правила — [`module-design.md`](module-design.md); соответствие прежним урокам М10A и М11_Cluster — ADR-0080 доп. 4 и раздел «Соответствие прежним урокам» в нормах каждого урока; прежние уроки удалены 2026-10-14 по слову владельца, две записи о решениях прежнего М11 — в `_notes-ru/`.

| № | Урок | Состояние |
|---|---|---|
| 1 | [Словарь операций хранилища](01-storage.md) — лекция; [нормы](spec/01-storage.norms.md), [дверь](spec/01-storage.api.openapi.yaml), [инструкция реализации](spec/01-storage.README.md) | образец новой формы (ADR-0080 доп. 2026-10-15) |
| 2 | [Спека подсистемы и строгий загрузчик](02-the-spec-and-the-strict-loader.md) — лекция; [нормы](spec/02-the-spec-and-the-strict-loader.norms.md), [дверь](spec/02-the-spec-and-the-strict-loader.api.openapi.yaml), [инструкция реализации](spec/02-the-spec-and-the-strict-loader.README.md) | новая форма по поручению владельца (2026-10-15) |
| 3 | [Единицы, строки, слоты, аренда](03-units-slots-epochs-lease.md) — лекция; [нормы](spec/03-units-slots-epochs-lease.norms.md), [дверь](spec/03-units-slots-epochs-lease.api.openapi.yaml), [инструкция реализации](spec/03-units-slots-epochs-lease.README.md) | новая форма по поручению владельца (2026-10-15) |
| 4 | [Контроллер и размещение](04-the-controller-and-placement.md) — лекция; [нормы](spec/04-the-controller-and-placement.norms.md), [дверь](spec/04-the-controller-and-placement.api.openapi.yaml), [инструкция реализации](spec/04-the-controller-and-placement.README.md) | новая форма (2026-10-15) |
| 5 | [Воркер под слотом](05-the-worker-under-its-slot.md) — лекция; [нормы](spec/05-the-worker-under-its-slot.norms.md), [инструкция реализации](spec/05-the-worker-under-its-slot.README.md) | новая форма (2026-10-15) |
| 6 | [Права](06-rights.md) | в main (2026-10-14) |
| 7 | [Секреты и запечатывание](07-secrets-and-sealing.md) | в main (2026-10-14) |
| 8 | [События, ресурс, база событий, единое хранение](08-events-resource-requests.md) | в main (2026-10-14) |
| 9 | [Консоль](09-the-console.md) | в main (2026-10-14) |
| 10 | [Схема, дренаж, снимки, пределы](10-schema-drain-snapshot-limits.md) | в main (2026-10-14) |
| 11 | [Платформа на коробке и на кластере](11-the-platform-on-a-box-and-a-cluster.md) | в main (2026-10-14) |

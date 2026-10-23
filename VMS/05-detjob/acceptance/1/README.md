# Приёмка V/05.1 — задача — единица

Норма главы — [`05.1-detjob.norms.md`](../../spec/05.1-detjob.norms.md) Н5. Стенд и словарь — [общий README приёмки
VMS](../../../common/acceptance/README.md) поверх общего README платформы (выгрузка `db53315`).

## Подготовка

Хранилище и консоль кластера; установлены манифесты `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`
(заказчик строк `detjob`), `VMS/04-det/det.subsystem.yaml`, `VMS/05-detjob/detjob.subsystem.yaml`,
`VMS/07-auto/auto.subsystem.yaml`; консоль — `CONSOLE_ROOT=detjob` (дверь `/jobs`), `rec` смонтирован (`console2` — префикс
`/rec`). Контроллер, воркеры, ресурс и домен не запущены. Запросы — с петли без домена (одна личность с полными правами).
Сценарий — на чистом экземпляре.

| Сценарий | Норма | Что наблюдает |
|---|---|---|
| `01-create` | V/05.1-01, V/05.1-02 | задача с умолчаниями `labels`, `alarms`; запись другой камеры — 409 `must_match`; `rec` не меняется; имя заказчика `rec-…` — 400 |

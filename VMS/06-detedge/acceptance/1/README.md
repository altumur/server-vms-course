# Приёмка V/06.1 — обход — единица

Норма главы — [`06.1-detedge.norms.md`](../../spec/06.1-detedge.norms.md) Н5. Стенд и словарь — [общий README приёмки
VMS](../../../common/acceptance/README.md) поверх общего README платформы (выгрузка `d3f8e05`, пин VMS).

## Подготовка

Хранилище и консоль кластера; установлены манифесты `VMS/01-cam/cam.subsystem.yaml`, `VMS/02-rec/rec.subsystem.yaml`,
`VMS/06-detedge/detedge.subsystem.yaml`; консоль — `CONSOLE_ROOT=detedge` (дверь `/watches`), `rec` смонтирован (`console2` —
префикс `/rec`). Контроллер, воркеры, ресурс и домен не запущены. Запросы — с петли без домена. Сценарий — на чистом
экземпляре.

| Сценарий | Норма | Что наблюдает |
|---|---|---|
| `01-create` | V/06.1-01, V/06.1-02 | обход с умолчаниями `alarms`, `start`, `keep`, `pre`/`post`/`join`; `start` и `keep` не из перечня — 400; `cam` не меняется; `rec` другой камеры — 409 `must_match` |

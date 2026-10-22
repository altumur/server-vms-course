# Платформа

Модуль уроков-спецификаций платформы, нарезанный по микромодулям: один урок — один процесс или библиотека (ADR-0083).
Каталог урока — `NN-<процесс>`; номер урока — адрес владельца (`P/NN`), карта — [`lessons.tsv`](lessons.tsv).
Общее для всех — [`common/`](common/README.md). Проектная записка — [`module-design.md`](module-design.md).

| P | Каталог | Микромодуль |
|---|---|---|
| 01 | [`01-store/`](01-store/README.md) | Хранилище |
| 02 | [`02-installer/`](02-installer/README.md) | Манифест и установщик |
| 03 | [`03-worker/`](03-worker/README.md) | Воркер (SDK) |
| 04 | [`04-controller/`](04-controller/README.md) | Контроллер |
| 05 | [`05-resource/`](05-resource/README.md) | Ресурс |
| 06 | [`06-console/`](06-console/README.md) | Консоль кластера |
| 07 | [`07-console-module/`](07-console-module/README.md) | Модуль консоли |
| 08 | [`08-domain/`](08-domain/README.md) | Процесс domain |
| 09 | [`09-agent/`](09-agent/README.md) | Агент (9.1) и режим ретранслятора (9.2) |
| 10 | [`10-domain-console/`](10-domain-console/README.md) | Консоль домена |

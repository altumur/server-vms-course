# Платформа

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

Модуль уроков-спецификаций платформы, нарезанный по микромодулям: один урок — один процесс или библиотека (ADR-0083).
Каталог урока — `NN-<процесс>`; номер урока — адрес владельца (`P/NN`), карта — [`lessons.tsv`](../lessons.tsv).
Общее для всех — [`common/`](../common/ru/README.md); слои В7 — [`common/LAYERS.md`](../common/ru/LAYERS.md), закреплённые версии библиотек — [`common/versions/`](../common/ru/versions/README.md). Проектная записка — `Platform/module-design.md` (для человека, в выгрузку не входит).

| P | Каталог | Микромодуль |
|---|---|---|
| 01 | [`01-store/`](../01-store/ru/README.md) | Хранилище |
| 02 | [`02-installer/`](../02-installer/ru/README.md) | Манифест и установщик |
| 03 | [`03-worker/`](../03-worker/ru/README.md) | Воркер (SDK) |
| 04 | [`04-controller/`](../04-controller/ru/README.md) | Контроллер |
| 05 | [`05-resource/`](../05-resource/ru/README.md) | Ресурс |
| 06 | [`06-console/`](../06-console/ru/README.md) | Консоль кластера |
| 07 | [`07-console-module/`](../07-console-module/ru/README.md) | Модуль консоли |
| 08 | [`08-domain/`](../08-domain/ru/README.md) | Процесс domain |
| 09 | [`09-agent/`](../09-agent/ru/README.md) | Агент (9.1) и режим ретранслятора (9.2) |
| 10 | [`10-domain-console/`](../10-domain-console/ru/README.md) | Консоль домена |

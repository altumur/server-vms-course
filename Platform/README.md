# Платформа

Модуль уроков-спецификаций платформы, нарезанный по микромодулям: один урок — один процесс или библиотека (ADR-0083).
Каталог урока назван именем процесса; номер урока — адрес владельца (`P/NN`), карта — [`lessons.tsv`](lessons.tsv).
Общее для всех — [`common/`](common/README.md). Проектная записка — [`module-design.md`](module-design.md).

| P | Каталог | Микромодуль |
|---|---|---|
| 01 | [`store/`](store/README.md) | Хранилище |
| 02 | [`installer/`](installer/README.md) | Спека и установщик |
| 03 | [`worker/`](worker/README.md) | Воркер (SDK) |
| 04 | [`controller/`](controller/README.md) | Контроллер |
| 05 | [`resource/`](resource/README.md) | Ресурс |
| 06 | [`console/`](console/README.md) | Консоль кластера |
| 07 | [`console-module/`](console-module/README.md) | Модуль консоли |
| 08 | [`domain/`](domain/README.md) | Процесс domain |
| 09 | [`agent/`](agent/README.md) | Агент (9.1) и режим ретранслятора (9.2) |
| 10 | [`domain-console/`](domain-console/README.md) | Консоль домена |

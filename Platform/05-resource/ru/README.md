# Ресурс — урок P/05

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом.

Микромодуль: процесс на сервере. Что нормирует и откуда — записка модуля `Platform/module-design.md` (judge-only: состав уроков для человека), таблица «Lessons».

Раскладка каталога (английский источник — на каноническом пути, русский текст для человека — в `ru/`):

```text
README.md                           этот файл
spec/05-resource.norms.md           нормы (одна глава)
spec/05-resource.api.openapi.yaml   двери
spec/05-resource.README.md          инструкция реализации
lifecycle.md                        флаги, окружение, коды выхода, юниты
forms/runtime-constants.tsv          независимые уставки; HTTP-значения — в OpenAPI
data/<семья>.schema.json            семьи данных, которыми урок владеет (JSON Schema 2020-12), с .layers.tsv, .outcomes.tsv
vectors/relieve/                    векторы алгоритма, который урок вводит
acceptance/                         приёмка урока (README.md, scenarios.tsv, inputs/)
ru/                                 для человека, в выгрузку не входит — лекция ru/05-resource.md, переводы английского текста тем же путём
```

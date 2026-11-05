# Манифест и установщик — урок P/02

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом (ADR-0121).

Микромодуль: процесс-команда, центр, юниты. Что нормирует и откуда — записка модуля `Platform/module-design.md` (для человека, в выгрузку не входит), таблица «Уроки».

Раскладка каталога (ADR-0124: английский источник — на каноническом пути, русский текст для человека — в `ru/`). Своего OpenAPI у установщика нет — HTTP-дверей у него нет;
`GET /manifest`, `ManifestView` и `ConsoleRefusal` при переносе урока 2 переехали временно в М10/9, переносом урока 6 — в [главу 6.5](../../06-console/ru/spec/06.5-console.norms.md) консоли
(ревью стадии A 2, П10):

```text
README.md                            этот файл
spec/02.K-installer.norms.md         нормы (главы 2.1–2.5 — .K)
spec/02.1-installer.schema.json      источник формы главы 2.1 (с .relations.json, .layers.tsv, .scalars.tsv; ADR-0092)
spec/02.2-installer.view.schema.json схема канонического вида главы 2.2
spec/02-installer.README.md          инструкция реализации
lifecycle.md                         флаги, окружение, коды выхода, юниты
forms/README.md                      колонки форм и грамматика швов без HTTP
forms/daemon-flags.tsv                имена, типы и условия опций команд
forms/operator-commands.tsv           id команд, префиксы argv и число аргументов
forms/refusals.tsv                    канонический каталог отказов глав 2.1–2.5
forms/stages.tsv                      план реализации (ADR-0126)
forms/rollout-poll.machine.yaml      формы ADR-0120 (автомат опроса обхода с трассами rollout-poll.traces.tsv)
data/<семья>.schema.json             семьи данных, которыми урок владеет (JSON Schema 2020-12, ADR-0092; ADR-0088)
vectors/<алгоритм>/                  векторы алгоритмов, которые урок вводит
acceptance/1/                        приёмка главы 2.1 (README.md, verdicts.tsv, classes.tsv, diagnostics.tsv, cases/)
acceptance/2/, acceptance/3/         приёмка глав 2.2, 2.3 (README.md, puts.tsv, puts/)
acceptance/5/                        приёмка главы 2.5 (README.md, scenarios.tsv, variants/)
acceptance/1/seams.tsv, acceptance/4/seams.tsv  дополнительные швы ядра, команд и опроса для тестов пакета
journal/corrections-<K>.tsv          журнал исправлений ИИ главы K — история, не вход; в выгрузку не входит
ru/                                  для человека, в выгрузку не входит — лекция ru/02-installer.md, переводы английского текста тем же путём
```

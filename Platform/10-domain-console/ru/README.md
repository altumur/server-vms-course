# Консоль домена — урок P/10

Текст производный от `README.md`, руками не правится: источник — английский [`README.md`](../README.md), правка идёт в него, русский пересобирается переводом.

Микромодуль: процесс domainconsole. Что нормирует и откуда — записка модуля `Platform/module-design.md` (judge-only: для человека, в выгрузку не входит), таблица «Уроки».

Раскладка каталога (английский источник — на каноническом пути, русский текст для человека — в `ru/`):

```text
README.md                                 этот файл
spec/10-domain-console.norms.md           нормы
spec/10-domain-console.api.openapi.yaml   двери
spec/10-domain-console.README.md          инструкция реализации
lifecycle.md                              флаги, окружение, коды выхода, юниты
data/refusal-words.tsv                    закрытый перечень слов error своих дверей (N4)
vectors/alarms/                           векторы списка тревог, функция alarms (N1.8, N3)
acceptance/                               приёмка урока, сц. 02, 05–19 (README.md, scenarios.tsv)
ru/                                       для человека, в выгрузку не входит — лекция ru/10-domain-console.md, переводы английского текста тем же путём
```

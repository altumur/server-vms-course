# C5 — учётки шлюза, runtime книг и role TLS

1. **Форма:** ADR-0074 C5, b2204ff6 и557540a8; точные выдержки в [FORM.md](FORM.md).
2. **Код:** `codex/course-c5-integrated`, база main03b68b8a после разрешённого М10/1; продукт не меняется.
3. **Чтение:** независимые пробы исправлены; итоговый diff Архитектору ещё не подан, разрешения слияния C5 нет.
4. **Прогон:** targeted101/0/0; полный combined: unit Python1983 + JS42 =2025/0/0, Cluster117/0/0, Domain228/0/0, DomainVMS164/0/0; все шесть exit0. После прогона все1006 файлов Source совпали с исходным снимком.
5. **Слияние и приёмка:** C5 в main не влит; настоящий HTTP/TLS, PERSON JWT, signed reports, CarryClient и RTSP проверяются тестами; работающий стенд продукта не менялся.
6. **Запись и отложенное:** логи вне репозитория, пути ниже; C6/C6b/C7 остаются отдельными окнами, новые уроки М10 ждут C7 по55d7e153.

Окончательный прогон пишет в
`/Users/murat/w2c/course-book-merge-evidence/c5-runtime-integrated/`.
Команды, env, PID и exit — `*.run.json`, `checks-integrated.json`, `*.exit`;
Source снимок — `source-integrated.json`.
Раннер [run_full_checks.py](run_full_checks.py) не пишет логи в git.

Первый полный красный прогон runtime сохранён отдельно:
`/Users/murat/w2c/course-book-merge-evidence/c5-runtime-standalone/`;
`sha256-manifest.json` фиксирует все74 файла. Его Source не менялся во время
проверок. Ошибки: отсутствующий начальный индекс имён в старых стендах,
посторонние спеки в каталоге generic тестов, недостающая группа livedomain,
гонка проверки метрики после освобождения прохода. Эти результаты не считаются
приёмкой исправленного combined Source.

Исправления тестов не создают индекс вручную: интеграционные стенды проходят
enrollment, подписанные отчёты и настоящий Holder.run_pass; отсутствие,
повреждение и частичный набор отчётов по-прежнему отказывают в записи гранта.
Изоляция каталога opt-in, восстанавливает состояние и сохраняет discovery.
Новые имена и исключения в загрузчике ради прохождения тестов не вводились.

Граница TLS C5 утверждена решением10b3a2d6: явный HTTP-режим коробки
или один установочный CA. Разные CA отказывают на handshake без обходов;
окна3/4 ADR-0075 зеркалируются отдельным общим этапом после C7.
Пути и SHA256 всех артефактов полного прогона —
[evidence-integrated.json](evidence-integrated.json).

## Approved correction cdd2c1f5

Architect approved C5 after removing worker.writes from testsub2 entirely;
door.pass:[entries] remains. The spec and two tests now forbid worker writes
to tallies and shelves, preserving worker.requests. Final targeted checks:
43 passed, 0 failed, 0 skipped, exit0. Initial64/2/0 retained: two obsolete
expectations required the removed grant; console_load passed.
X-Operator is confirmed as an outgoing console header; incoming headers
are removed. Supersedes the pending-review/operator statuses above.
See evidence-approved-correction.json for commands, log paths and SHA256.

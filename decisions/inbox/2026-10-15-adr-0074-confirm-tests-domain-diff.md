---
kind: отчёт
adr: 0074
date: 2026-10-15
author: команда курса (OpenAI Codex)
---

# ADR-0074: diff подтверждения границы тестов

Ветка `codex/course-adr74-confirm-tests-domain`, база `dcf2509c`, diff проверок — до `6c34f581`. Все проверки из `tests/domain` больше не импортируют VMS; `TESTS.tsv` покрывает 192 проверки и сохраняет 742 узла `assert`. Runtime платформы и продукт не менялись.

Результаты: domain 190/0, domainvms 206/0; unit 2050/1/2 — единственный отказ `platform_lists` (ожидаемое расхождение паритета), два пропуска console без jsdom. Журналы и SHA256: `windows/adr74-confirm/evidence.json`. Готово к чтению; слияние не выполнялось.

## Решение («Архитектор», 2026-10-17)

Diff `dcf2509c...6cfedaff` прочитан. Сверено независимо: приёмочный `grep` пуст; `test_tests_domain_does_not_import_vms`
зелёный и срабатывает на подложенный `importlib.import_module("vms.config")` (строковое имя модуля ловится); утверждений
по AST в `tests/domain` + `tests/domainvms` 1679 до и 1679 после (857 + 822 → 712 + 967); 192 строки `TESTS.tsv` сходятся
с кодом по обеим сторонам (742 → 742, ни одна цель не делится двумя строками); повтор на `6cfedaff`: domain 190/0/0,
domainvms 206/0/0 (`OBSD_BIN` — сборка 2026-10-14); unit не повторялся. Исполняемый код платформы и продукт не тронуты;
с `main` ветка сливается без конфликтов.

**Стенд камеры в `tests/domain` (решение владельца 2026-10-17):** фикстура может загружать опубликованную спеку `cam`
из `Source/vms` — «для тестирования использование реальной подсистемы вполне допустимо». Граница пункта Confirmation —
импорт кода `vms` (её держит `test_boundary.py`), не чтение спеки. Записано в ADR-0074, дополнение 2026-10-17.

**Поправки той же веткой до слияния** (без нового решения):
1. **Строки таблицы.** 13 изменённых проверок без строки в `TESTS.tsv`: `test_lesson1_directory_and_placement.py` — 10
   (`test_where_across_three_clusters_…`, `…_honest_about_ids`, `…_incomplete_not_short`, `…_fault_not_a_tie`,
   `…_mid_move_…`, `…_reachability_then_headroom`, `…_never_named_one`, `…_racing_agree_by_cas`, `…_not_a_trigger`,
   `…_domain_holder_is_designated`), `test_lesson2_shadow.py` — 3 (`test_the_taxonomy`, `test_slow_versus_stuck`,
   `test_exit_criterion_is_written_down`). Изменение без строки — то же, что удаление без строки.
2. **Ослабленная проверка.** `test_the_cluster_then_places_on_a_worker_and_the_domain_never_named_one` доказывала выбор
   воркера по достижимости (`"reaching vlan:b" in where.reason`); теперь — `"most free capacity"`, и метки вручную
   поставлены обоим воркерам. У `testsub` `constraint: labels-subset`, и `SpecController` пишет `reaching <labels>`
   (`spec.py`, причина размещения) — вернуть доказательство на `testsub` с одним воркером, достигающим `vlan:b`, и одним —
   нет; либо назвать дубликат (а) по имени.
3. **Загружать только `cam`.** `_ensure_camera_spec` (`tests/domain/conftest.py`) и `device_console`
   (`tests/member_console.py`) зовут `catalog.load_dir(Source/vms)` — в каталог процесса попадают все четыре спеки VMS
   (`cam`, `rec`, `live`, `auto`), и следующие проверки платформенного домена видят их в `declared.specs()`. Грузить один
   `cam.subsystem.yaml` (`catalog.register` спеки, прочитанной из файла).
4. **Докстринги говорят правду.** `EmbeddedMember`: «does not load a subsystem spec» — неверно, спеку `cam` он грузит;
   написать, что грузит и зачем. В `test_lesson1_directory_and_placement.py` и `test_lesson2_shadow.py` импорт
   `isolated_catalog` стоит до докстринга модуля; в `snapshot` и `heartbeat` вызов `_ensure_camera_spec()` — до докстринга
   функции: докстринги перестали быть докстрингами.
5. **Правки вне окна названы.** `test_console_gate.py` (`metrics_text` у подделки `RecWorker`) и `test_row_reader.py`
   (`ingest` у подделки) — в отчёте ни слова. Назвать, почему (какую проверку unit на `dcf2509c` они чинят), или снять.

После поправок — повтор domain, domainvms, boundary и unit (с единственным `platform_lists`), обновлённые `TESTS.tsv` и
`evidence.json`, хеш ветки — здесь же, разделом «Исполнение». «Архитектор» сверяет поправки 1–5, разрешает слияние и
закрывает пункт Confirmation в ADR-0074.

## Исполнение (команда курса, 2026-10-17)

Ветка `codex/course-adr74-confirm-tests-domain`, проверенные код и доказательства — `9d1f5f23`.
Решения из main влиты; оба конфликта add/add входящих разрешены версией main.

1. `TESTS.tsv`: добавлены все 13 проверок (урок 1 — 10, урок 2 — 3), судьба каждой названа.
   Итого 205 уникальных целей, 786 → 786 узлов `assert`; во всех тестовых модулях domain + domainvms
   1679 → 1679 (857 + 822 → 712 + 967).
2. В `test_the_cluster_then_places_on_a_worker_and_the_domain_never_named_one` только `w-1` достигает `vlan:b`;
   проверяются ровно `w-1`, причина `reaching vlan:b` и сервер `srv-10`. Исполняется testsub с `labels-subset`.
3. По уточнению `643d5223` `_ensure_camera_spec` читает исходную cam и её соседа из `camera.near`.
   `device_console` использует тот же загрузчик. Из пустого каталога получены только cam и rec, контроллер строится;
   live/auto не загружаются, спеки не изменяются, `load_dir(Source/vms)` не используется.
4. Докстринги EmbeddedMember и загрузчика называют cam, объявленного соседа rec и ADR-0056.
   Докстринги модулей уроков 1–2 и функций snapshot/heartbeat снова стоят первыми.
5. Две правки вне исходного окна сохранены как исправления отставших тестовых двойников на базе `dcf2509c`:
   - `test_console_gate.py::test_the_door_in_is_the_consoles_alone_and_takes_a_token_or_an_emergency_entry_and_nothing_else`:
     `RecWorker.serve_archive` при создании двери читает `self.metrics_text`; поддельному RecWorker добавлен пустой
     callback, без которого был AttributeError до проверки двери.
   - `test_row_reader.py::test_a_name_with_a_quote_or_a_newline_is_escaped_on_every_metrics_page`:
     `RecWorker.metrics_text` читает `self.ingest`; двойнику добавлен `ingest=None`, без которого был AttributeError
     до проверки экранирования. Утверждения обоих тестов не менялись.

В двух проверках урока 10 ожидания flash уточнены под фактически загруженные cam/rec: четыре книги вместо шести;
сохранены точный бюджет начальных записей, точный список всех строк и проверка отсутствия лишних записей за сутки.
Изменения названы в соответствующих строках TESTS.tsv; утверждений не убавилось.

Повторы: domain **190/0/0**, domainvms **206/0/0**, boundary **6/0/0**; unit **2047/4/2**.
Один отказ unit — ранее разрешённый product-parity `platform_lists`; три дополнительных:
- внутренняя сверка `secret_roles`: main `92a0f988` убрал domainpart из TSV, код и ADR-0074 его сохраняют;
- две проверки `test_storage_m10`: шаг 22-body-edge, `body.limit` 524288 вместо 1048576, закреплённого Н5 приёмки.

Условие «unit с единственным product-parity» **пока не выполнено**. Диагнозы и рекомендации до кода:
`2026-10-17-confirm-secret-roles.md`, `2026-10-17-confirm-body-limit.md`. Исправлений общей таблицы или runtime
без решения не делали. Все 1123 файла Source совпали с сохранённым SHA256-манифестом после прогонов.

Журналы вне репозитория, команды и SHA256 — `windows/adr74-confirm/evidence.json`.
Платформенный runtime, опубликованные спеки и продукт не изменялись. Слияние в main не выполнялось; diff к повторному чтению.

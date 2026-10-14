# Окно Python-хранилища М10/1

База: `ccfffb6656059960fd157e435554275d4c5a5e8c`.
Решение: `decisions/inbox/2026-10-14-мутационная-проба-м10.md`.
Код платформы остаётся в `codex/course-m10-storage` до чтения Архитектором.
Команда окна не меняла продукт, новые уроки и общую приёмку.
Обновления Спецификации приняты неизменными через merge origin/main.
Checkpoint кода: 7d9328dea2b05772ccba89e81eaba5ec710b7bed.
Merge свежего main: 3ca2eba3ed52adb1bef166652ee623b1e614b227 (origin 0a867703).
Production storage и оба новых helper/test файла побайтно совпадают с checkpoint.

## Сделано

Дверь: закрытый Fault, string index/get/list/write/conflict/guard, kind guard,
again при повторе, строгие cas/id/items, пустой страж, поля потолка.
Внутренние индексы журнала и публичных Python handles числовые; единственный
переход к строкам выполняется на HTTP-границе. Это не двойное чтение старого
провода: числовой cas/index на HTTP отказан.

Backup сравнивает числовые bookkeeping indexes после явного преобразования,
иначе строковые wire versions ломали max. File.delete резервирует счётчик
до удаления последней строки: пропавший counter отказывается до потери ряда.

Source/tests/storage_acceptance.py использует неизменный TSV и реальный StoreDaemon в отдельном
Python-процессе через unix HTTP. Matcher дополнен обязательным JSON-string
для любого $var по актуальному shared README; остальное точное сравнение
JSON с исключением неназванного error. 98/98 шагов зелёные, все54 numericwire
наблюдения исчезли. Артефакты: acceptance/api.json, daemon.json, api-calls.json.

Шесть независимых проверок tests/test_storage_m10.py: create/delete/create/staleCAS
для File/Mem; потеря counter перед delete последнего ряда; ровно512КиБ без
заимствования MAX_VALUE из реализации; fsync reservation перед unlink;
отказ counter ниже начального floor; реальный shared API daemon process.

## Ещё не выполнено

Второй исполнитель тех же сценариев через публичный File/Mem API требует
реального optional id/replay и возвращаемой версии delete. Их сейчас нет;
кэшировать ответы в тестовом адаптере означало бы подделать проверку backend.
Предложение до нового disk-контракта: decisions/inbox/2026-10-14-м10-api-повторы.md.
До решения этот участок не реализован и окно не объявлено закрытым.

## Проверки

Фактические логи сохраняются рядом. target.log — исходные отказы старых
wirefixtures плюс найденный backup regression; target2.log — уточнение одной
fixture id; target3.log содержит ещё старую direct-wire numeric CAS fixture,
исправленную затем. Эти исходные прогоны не объявляются зелёными.
Результат промежуточного checkpoint, а не закрытие окна:

| Прогон | Успех / отказ / пропуск | Exit |
| --- | --- | --- |
| HTTP shared acceptance | 98 / 0 / 0 шагов | 0 |
| Cluster-final | 117 / 0 / 0 | 0 |
| Domain-final | 228 / 0 / 0 | 0 |
| DomainVMS-final | 166 / 0 / 0 | 0 |
| unit-final, включая 40 native JS | 1940 / 1 / 0 | 1 |
| target-fixed-final | 47 / 0 / 0 | 0 |
| durable-resumed (после возобновления) | 5 / 0 / 0 | 0 |

Единственный отказ unit-final: test_store_durable ожидал два directory fsync,
а резервирование версии перед изменением ряда требует третьего. Исправлена
только fixture (95b451ae): точные file=2/dir=3, после второго writer file=4/dir=6.
Целевые 47 проверок и отдельные пять durable подтверждают исправление.
Полный unit после этой fixture ещё не повторялся; результат 1940/1 сохранён
без переименования в зелёный. Нативные JS в этом прогоне: 40/40.

Код production и новые helper/test не менялись после 7d9328de.
Итоговый Source checkpoint с исправленной fixture: 95b451ae.
Точные SHA256 Source и артефактов: evidence.json. Старые красные/прерванные
прогоны сохранены как диагностика, не как приёмка.

Воспроизведение из Source/: Python — /Users/murat/w2c/vms-nightly/venv/bin/python;
OBSD_BIN=/Users/murat/w2c/vms-nightly/exe/obsd, PYTHONUNBUFFERED=1;
W2C_PRODUCT_REF не задан. Команда целевой независимой проверки:
`python tests/run.py test_store_durable`.
Общий целевой прогон: `python tests/run.py test_store_durable test_storage_m10 test_guard test_storemachine test_body_fault_doors`.
HTTP: `python tests/storage_acceptance.py <output-directory>`.

Пока не закрыто: решение о публичном File/Mem write receipt и форме повторов,
реальный второй исполнитель TSV без двери, приёмка обоих storage backends,
итоговый полный unit, чтение diff Архитектором. Общая регистрация новых
storage_acceptance/test_storage_m10 остаётся у владельца test_boundary.py.
Уточнение API — 957c7350, опубликовано владельцем в main как 801e4c39;
без раздела «Решение» API и дисковая форма не реализуются.

## Конкурентные изменения main

Спецификация удалила прежние М10A/М11_Cluster и их quote-test. Source/traces
пересняты честно; до обновления main один quote-test отказывал старым цитатам.
Предложение расширить исключение чисел до JSON-кавычек (184fdb47) отозвано
(4f6527a7), не публиковалось: уроков и самого теста уже нет в main. Их удаление
не сделано нашим окном. После merge main полный Cluster содержит117 тестов
вместо121: четыре проверки старых цитат сняты Спецификацией.

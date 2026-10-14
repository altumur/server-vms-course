# М10/1 — итог окна File/Mem и приёмка

Архитектор разрешил интеграцию до C5 в `9a4fb347`, раздел «Решение» файла
`decisions/inbox/2026-10-14-м10-финальный-diff.md`.
Ветка: `codex/course-m10-storage`. Проверенный Source checkpoint:
`13ca0880472e850f8f76219aab1a377ec06ada09`; Source tree:
`f91530b2ee00853c37072550f8b858fce2716e2d`.
Продукт не менялся; новые уроки, shared TSV/README, спеки и модуль консоли
этим окном не редактировались. Платформа командой окна в main не влита.

## Реализация

Пять платформенных файлов исполняют решения b2204ff6 и c17ec273:
`configstore.py`, `configstorevars.py`, `memvariables.py`, `storemachine.py`,
`variables.py`. Остальной Source diff — тесты, исполнитель того же TSV и
20 переснятых trace-файлов.

File/Mem предоставляют настоящий `write(cmd) → {index, again}`; put/delete
оборачивают его, delete возвращает выданную версию. Native версии остаются
непрозрачными native значениями, отсутствующий ряд —0; на проводе версии —
строки JSON. Отказаны числовой wire CAS, неверные id/items/guard; Fault закрыт,
лишнего поля fault нет. Counter резервируется долговечно до unlink, поэтому
удаление последнего ряда не позволяет повторить прежнюю версию и принять старый CAS.

Память повторов общая у File handles одного directory identity и у handles
одного Mem state, только в процессе: не меньше120 секунд и последних50000
ответов. Права проверяются до памяти; другой payload того жеid отказан.
CAS/guard проверяет backend атомарно, а повтор получает прежний receipt,
не проверяя версии заново. Receipt и items копируются. На диске нет новых
replay records, WAL или tombstones; перезапуск разрешённо забывает память.

После rename/unlink receipt регистрируется под replay/file locks до оставшихся
барьеров. Поздний OSError — существующий StoreAmbiguous, в HTTP-нотации503
ambiguous. Строка остаётся видимой. Повтор довершает только оставшиеся барьеры
исходного writer, даже через volatile handle; не изменяет target, не выдаёт
новую версию и не повторяет CAS/guard. Повторный отказ барьера снова ambiguous.
Ошибка до публикации не создаёт ложного receipt. Mem не изобретает fsync.

List перечисляет имена/версии без read-фильтра; исчезнувшая между list/get
строка пропускается. Общий предел ключа —1024 UTF-8 bytes; encoded filename
limit246 применяется только File к target/guard. Порядок key → weight → ACL
проверен. Исправлены также backup bookkeeping после строкового wire index
и перенос max_bytes в File.as_writer.

## Окончательная приёмка

| Набор | Успех / отказ / пропуск | Exit |
| --- | --- | --- |
| Unit part1 | 1071 / 0 / 0 | 0 |
| Unit part2 | 845 / 0 / 0 | 0 |
| JS | 40 / 0 / 0 | 0 |
| Unit вместе с JS | 1956 / 0 / 0 | 0 |
| Cluster | 117 / 0 / 0 | 0 |
| Domain | 228 / 0 / 0 | 0 |
| DomainVMS | 166 / 0 / 0 | 0 |
| Shared HTTP | 98 / 0 / 0 шагов | 0 |
| Shared File | 98 / 0 / 0 шагов | 0 |
| Shared Mem | 98 / 0 / 0 шагов | 0 |
| Target storage/durable/Mem | 30 / 0 / 0 | 0 |

[checks-pending.json](checks-pending.json) содержит exact module lists и команды:
две непересекающиеся части в объединении дают все Source/tests/test_*.py,
JS выполнен отдельно. Python: `/Users/murat/w2c/vms-nightly/venv/bin/python`;
`OBSD_BIN=/Users/murat/w2c/vms-nightly/exe/obsd`, `PYTHONUNBUFFERED=1`,
`W2C_PRODUCT_REF` удалён. Полные запуски выполнялись `run_final_checks.py pending`.
Shared: из Source `tests/storage_acceptance.py <output> --backend http|file|mem`.
Для нового прогона используйте внешний каталог вывода, не git-окно.

HTTP использует реальный StoreDaemon в другом процессе и unix socket;
File/Mem проходят те же неизменные98 шагов через публичный write/get/list,
без двери и без тестового replay. Matcher сравнивает closed JSON, кроме
неназванного error; любая $var обязана быть JSON string. Native адаптер
переводит нотацию/исключения, не сравнивает CAS/guard и не хранит ответы.
Body/route facets адаптера не выдаются за независимый HTTP transport test.

21 storage witness проверяет ABA, независимый literal512KiB ceiling,
counter/fsync ordering, replay/retention, процесс, конкурентные handles,
list races, key bounds, приоритет отказов и pending receipt File/Mem.

## Внешние свидетельства и история

Архив всех190 исходных файлов окна на e404246b:
`/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/`.
[README.md](README.md) содержит путь и SHA256 внешнего manifest;
[evidence-locations.json](evidence-locations.json) — retained/external карту
всех189 хешей исходного [evidence-final.json](evidence-final.json).
Оригиналы обновлённых документов также сохранены во внешнем snapshot.
Все последующие ссылки ниже ведут во внешний архив.

- [Полные exact команды и env](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/unit-pending-part-1.run.json), [проверка неизменности Source](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/source-unchanged.json), [хеши Source](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/source-pending.json).
- [Первый независимый аудит](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/m10-checkpoint-review.md) нашёл read-фильтр list, пустую absent version при гонке и File key limit в Mem; все исправлены в3569935c.
- [Независимый pending аудит](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/m10-pending-review.md) блокирующих замечаний не нашёл: отдельный storage21/0/0 и [внешняя проба](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/m10-pending-review-probe.log) exit0. Матрица put/delete×vars/root, повторные отказы, volatile handle, смена target/guard, retention и os._exit проверены. Сама воспроизводимая [проба](m10-pending-review-probe.py) оставлена в git.

История не переписывается зелёной: unit47453a55 был1945/2/0, прежний unit95b —
1940/1/0. Исправлены File key-limit/fixture и durable fixture; отказ
lesson11_edge:857 отдельно не воспроизвёлся в33/0/0 и в финальном полном unit.
Причину старого отказа это не доказывает. Промежуточный356 был1952/0/0,
но дополнительная fault-инъекция выявила потерю receipt после fsync; принятая
поправка c17ec273 проверена окончательным13ca0880. Первый pending target упал
на отсутствии monkeypatch.context в custom runner; witness переведён на
stdlib mock/ExitStack. Все исходные красные логи и exit сохранены в архиве.
Exit0 исходной observational fsync-пробы означает воспроизведение дефекта,
а не успешную приёмку старого кода. Полная прежняя история и команды —
[исходный FINAL snapshot](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/FINAL.md).

## Интеграция и границы

Архитектор разрешил merge; владелец общей границы регистрирует
`storage_acceptance.py` и `test_storage_m10.py` в PLATFORM_TESTS, затем проверяет
объединённый Source. Команда storage этот общий файл и main не меняет.
Перенос логов — только запись окна, Source tree сохранён побайтно.
Реальная потеря питания и асинхронная отмена Python-потока не моделировались;
гарантия replay не распространяется на новый процесс по принятому решению.

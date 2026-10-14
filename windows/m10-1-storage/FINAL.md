# М10/1 — File/Mem, receipt и та же приёмка

Реализовано в ветке `codex/course-m10-storage`; в main платформа не влита.
Продукт не читался и не менялся вручную. Новые уроки, общие acceptance TSV/README,
спеки, общая регистрация тестов и файлы C5 этим окном не редактировались.

## Основание и diff

Решение Архитектора: `decisions/inbox/2026-10-14-м10-api-повторы.md`, раздел
«Решение» от 2026-10-14. Свежий main b2204ff6 принят merge 5e606c5b;
конфликт опубликованного API-уточнения разрешён точным файлом origin/main.

API checkpoint до независимого чтения: `47453a555d61aed8669339ab3c99de55166356ab`.
Промежуточный production checkpoint после исправлений независимого ревью: `3569935cde80ce0917b9bb03960dbaa88c535276`.
Финальный production checkpoint с согласованным pending receipt: `13ca0880472e850f8f76219aab1a377ec06ada09`.
Source tree: `f91530b2ee00853c37072550f8b858fce2716e2d`.
Свежий main c17ec273 принят merge18801f93, inbox Архитектора сохранён дословно.
Первый этап API после решения — четыре пофайловых коммита:

- 95114d42: File write/receipt, память повторов, возвращаемый index delete.
- 198f88f2: Mem write/receipt с той же семантикой.
- 7ef7ca76: второй исполнитель неизменного TSV через публичные File/Mem API.
- 47453a55: независимые проверки replay, процесса, конкуренции и обеих реализаций.

Ранее в этом окне исправлены wire index/Fault/guard/CAS/items, ABA последнего
удалённого ряда, барьеры counter reservation, wire fixtures и 20 честно переснятых
trace-файлов. Исправление durable fixture отдельно: 95b451ae. Полный diff окна
смотреть от ccfffb66; новый API-этап — `git diff 5e606c5b..47453a55 -- Source`.

## Реализация

`FileVariables.write(cmd)` и `MemVariables.write(cmd)` возвращают собственный
receipt `{index, again}`; при первом успехе again=false, при повторе true.
Публичные put/delete — обёртки без собственной памяти, принимают optional id;
delete возвращает выданную версию. Native versions сравниваются без изменения,
отсутствие ряда обозначено 0. Преобразование в строку — только в исполнителе
HTTP-нотации. Обычные put сохраняют преобразование полей items в строки,
write принимает уже подготовленный map[str,str].

CAS и guard проверяет backend в той же блокировке, что изменение строки.
Повтор определяется до повторной проверки CAS/guard, поэтому прежний успешный
ответ возвращается и после смены guard; другой write под тем же id отказан.
Память хранит также исходный Conflict/GuardFailed, не сравнивая заново с уже
изменённой строкой. Версия Conflict берётся из атомарной операции, а не из
второго чтения тестовым адаптером. Публичный receipt и items копируются.

Память повторов живёт с процессом: не меньше 120 секунд и не меньше последних
50 000 ответов. Удаляется только запись, которая старше 120 секунд и выходит
за последние 50 000. При высоком потоке в течение двух минут записей может
быть больше. File handles одного directory identity разделяют память процесса,
Mem — память общего _MemState; их ACL остаются на handles. File сохраняет
существующий файловый lock для разных процессов. В другом процессе повтор
забыт и применяется заново, если CAS позволяет. Никаких новых disk-record,
replay-файлов, WAL или надгробий не создано.

File as_writer теперь переносит max_bytes: другой writer не теряет заявленный
потолок того же хранилища.

## Исполнители и границы проверки

Один matcher и один проход по unchanged scenarios.tsv используются тремя
исполнителями: HTTP реального StoreDaemon в отдельном процессе; публичный
File API без двери; публичный Mem API без двери. Все три исполняют все 98 шагов.
Ответы сравниваются как closed JSON, кроме неназванного error; всякая $var
обязательно связывается с JSON string.

Native адаптер переводит request-нотацию, native версии и исключения в Fault.
Он не хранит id/ответов, не сравнивает CAS/guard и не меняет строки сам.
Wire grammar проверяется общими production check_write/check_key, не отдельной
копией правил. Чтение get использует существующий rights.refusal; список имён/версий не
требует read ACL (Н3 перечислить). Нативный интерфейс handles исторически
ограничивал записи, не get/list. Ошибочный фильтр в checkpoint47453a55
найден независимым ревью и исправлен в 3569935c.
Body bound и неизвестный route — проверка адаптера нотации, не файлового I/O.
Поэтому native прогон не выдаётся за независимую проверку HTTP-транспорта.
HTTP отдельно действительно проходит через unix socket чужого процесса.

21 tests/test_storage_m10.py проверяют ABA, потерю/нижний floor counter,
независимый потолок literal 512 KiB, порядок reservation fsync перед unlink,
три исполнения shared TSV, replay после смены guard, wrappers и receipts,
исходный cached conflict, границы 120 секунд/50 000, перезапуск File без replay,
отсутствие новых disk-record и четыре одновременных запроса одного id.
Native трассы фиксируют вызовы реальных write/_apply_write, не только matcher.

## Приёмка

Три standalone прогона acceptance-*-complete: HTTP 98/98, File 98/98, Mem 98/98,
каждый exit 0. HTTP readiness и exit собственного daemon сохранены отдельно;
File disk listing показывает только прежние index/lock/vars/*.json.
Target native-target-verified: 48 passed, 0 failed, 0 skipped; exit 0.

Четыре полных набора на checkpoint 47453a55 завершены: unit 1945/2/0 exit1,
включая JS 40/40; Cluster 117/0/0, Domain 228/0/0, DomainVMS 166/0/0 exit0.
Первый отказ — неверный ранний File key-limit ValueError вместо KeyTooLong;
исправлен и проверен целым test_garbled_rows. Второй — r.fetched в
lesson11_edge:857; без правок VMS полный отдельный модуль на исправленном
storage повторён: 33/0/0 exit0. Это не доказательство причины старого отказа.
Их исходный лог сохранён и не объявлен зелёным.

Все три acceptance-*-verified на checkpoint 3569935c: 98/98 exit0.
Focused target356: 130/0/0 exit0. Полные промежуточные unit:1067+845+JS40=1952/0/0;
Cluster117/0/0, Domain228/0/0, DomainVMS166/0/0, все exit0.
source-verified.json фиксирует весь Source356; checks-verified.json — точные
непересекающиеся полные списки модулей; каждый *.run.json содержит команду, pid и SHA.
Этот зелёный checkpoint не объявляется финальной приёмкой нового fsync fix.
На Source13ca0880 завершены новые полные прогоны *-pending с отдельными логами и
манифестами source-pending.json/checks-pending.json.

| Прогон | Успех / отказ / пропуск | Exit |
| --- | --- | --- |
| Unit part1 | 1071 / 0 / 0 | 0 |
| Unit part2 | 845 / 0 / 0 | 0 |
| Отдельный JS | 40 / 0 / 0 | 0 |
| Unit + JS суммарно | 1956 / 0 / 0 | 0 |
| Cluster | 117 / 0 / 0 | 0 |
| Domain | 228 / 0 / 0 | 0 |
| DomainVMS | 166 / 0 / 0 | 0 |
| HTTP shared steps | 98 / 0 / 0 | 0 |
| File shared steps | 98 / 0 / 0 | 0 |
| Mem shared steps | 98 / 0 / 0 | 0 |

Unit разбит по модулям на две непересекающиеся части: объединение в точности
все Source/tests/test_*.py; JS выполнен отдельно, не пропущен. Команды и полный
состав модулей — checks-pending.json и каждый *.run.json. Повторить проверку:
`/Users/murat/w2c/vms-nightly/venv/bin/python windows/m10-1-storage/run_final_checks.py <новый-суффикс>`
из корня worktree; скрипт отказывает перезаписи существующего лога.
Во всех child environments `OBSD_BIN=/Users/murat/w2c/vms-nightly/exe/obsd`,
`PYTHONUNBUFFERED=1`, `W2C_PRODUCT_REF` удалён. Три standalone shared выполнены
тем же Python: `tests/storage_acceptance.py <output> --backend http|file|mem`
из Source.

source-unchanged.json подтверждает все исходные SHA256 после завершения,
пустой Source diff и удаление временной node_modules symlink для JS.
evidence-final.json содержит итоговый snapshot артефактов; старый evidence.json
остаётся историческим снимком95b, его не переписывали. Target pending-target:
30/0/0 exit0. Предшествующий pending-target-fixture-red: custom runner не имеет
monkeypatch.context; исправлен только witness на stdlib mock/ExitStack. Старые прогоны сохранены как история:
unit-final был 1940/1 до исправления durable fixture, native-target exit 2
содержит ошибочное имя несуществующего test_variables. Они не зачтены зелёными.

## До интеграции

Архитектор должен прочесть платформенный diff ветки; в main его не вливать
до проверки. Владелец общей test_boundary.py добавляет storage_acceptance.py и
test_storage_m10.py в PLATFORM_TESTS; этот файл не принадлежит окну М10/1.
Новые имена на проводе или диске, кроме принятого публичного receipt, не вводились.

## Независимое чтение checkpoint 47453a55

Отчёт m10-checkpoint-review.md и исходный probes.log скопированы побайтно из
course-book-merge-evidence; Source/index/git аудитор не менял. Подтверждены:
read ACL ошибочно фильтрует list; гонка list→delete→get даёт пустую версию;
Mem наследует ранний encoded file limit вместо generic 1024 raw bytes.
Frozen прогон завершён до исправлений. Все три замечания исправлены отдельным
checkpoint 3569935c, дополнительное baseline-расхождение weight-before-ACL
также приведено к показанному алгоритму М10/1 (по согласованию владельца).
Generic key bound Machine/Mem/client — 1024 raw UTF-8 bytes; File сохраняет
собственный encoded filename bound 246 для target и guard. File put/delete
отказывают длинному ключу KeyTooLong, get такого ключа остаётся native absent.
Новый совместный witness доказывает badkey раньше oversized и 413 раньше ACL.
Проверены Mem/native adapter key300, UTF-8 1024/1025, unix wire client roundtrip,
guard и list-prefix длиннее файлового предела. Для list проверены чужие имена
без чтения значений и omission строки, удалённой между names и get.

## Согласованная fault-инъекция и pending receipt

После исправлений ревью выполнена отдельная проба fsync-replay-probe.log на
3569935c (volatile=False). Один OSError из directory barrier ПОСЛЕ rename:
первый write(id=e1) бросает ошибку, get уже видит index1001; немедленный повтор
того же write/id в том же процессе даёт index1002, again=false. Exit0 пробы
значит, что проба завершилась; это воспроизведение дефекта, не зелёная приёмка.

Предложение до кода: decisions/inbox/2026-10-14-м10-id-после-ошибки-fsync.md,
commit90795929. Архитектор принял рекомендацию в c17ec273, раздел «Решение».
Исполнение в 8f98ccd0/10d484c1/13ca0880: receipt регистрируется в process-memory
под replay+file locks после rename/unlink, до оставшихся directory barriers.
Поздний OSError — существующий StoreAmbiguous (OSError), в HTTP-нотации503
kind=ambiguous. Строка остаётся видимой; не откатывается и не получает новую
версию при повторе. Неуспешная повторная попытка барьера снова ambiguous.
После подтверждения повтор возвращает исходную версию с again=true.

Pending хранит исходное подтверждение долговечности и список оставшихся
барьеров. Успешный barrier исключается из повторов; другой volatile handle
не может обойти fsync исходного durable writer. Сравнения CAS/guard и изменение
строки не повторяются, даже если тем временем guard и целевая строка изменились.
Изменённый payload под тем жеid —400; write/guard-read ACL проверяются до
доступа к памяти. Ошибка до публикации не создаёт receipt. Mem использует
ту же память, но не изобретает барьеров/диска; нормальный replay подтверждён
теми же четырьмя witnesses. Новых replay-файлов, WAL или tombstones нет.

Четыре новых witness проверяют: File put/delete с одноразовым поздним отказом
и последующей сменой guard/CAS/target; повторные отказы последнего барьера и
ровно оставшиеся fsync, включая503 closed JSON; до-публикационный отказ без
ложного receipt; changed-payload400 и запрет доступа к памяти до ACL.
Все четыре применяются к File и Mem, у Mem подтверждается отсутствие fsync.
Старые diagnostic-пробы сохранены как воспроизведение356; они не выдаются
за зелёную приёмку исправленного кода.

## Независимое чтение pending receipt

[m10-pending-review.md](m10-pending-review.md) и внешний
[m10-pending-review-probe.py](m10-pending-review-probe.py) с
[логом](m10-pending-review-probe.log) скопированы побайтно из evidence владельца.
Аудит проверил именно Source13ca0880, блокирующих дефектов не нашёл;
отдельный test_storage_m10:21/0/0 exit0. Внешняя матрица put/delete × отказ
vars/root, повторные отказы, reopened volatile handle, изменившиеся target/guard,
age-only/count-only и границы retention, os._exit перед post-publication barrier
прошли exit0. Потеря process-memory при завершении процесса разрешена Решением;
новых disk-record нет. Реальная потеря питания и асинхронная отмена Python-потока
не моделировались; дополнительных гарантий отчёт не заявляет.

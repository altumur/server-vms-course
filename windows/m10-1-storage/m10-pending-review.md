# М10/1: независимое ревью pending receipt

Проверено Решение `c17ec273` и diff `3569935c..13ca0880`, только исправление pending receipt. Блокирующих дефектов не найдено. Source и продукт не изменялись.

Во время проверки HEAD storage worktree перешёл на `881f4b95` из-за записи внешних свидетельств; `git diff 13ca0880 HEAD -- Source` пуст, равно как diff проверенных файлов рабочего дерева с `13ca0880`. Проверенный runtime — ровно frozen Source `13ca0880`.

## Проверенные гарантии

| Участок | Наблюдение |
|---|---|
| Публикация put/delete | `variables.py:656–670`: `_next_index` резервирует индекс, put fsync-ит временный файл до rename; delete делает unlink. После публикации `_apply_write` возвращает исходный receipt. До завершения общей replay/file блокировки receipt регистрируется в `_Replay.done` и `.pending` (`:388–395`, вызов под обеими блокировками `:646–648`). Directory barriers идут после регистрации. |
| Исходный неоднозначный исход | `_Replay.finish`, `variables.py:408–415`: OSError от post-publication barrier преобразуется в `StoreAmbiguous`. Строка не откатывается, pending остаётся. `storage_acceptance.py:295–299` переводит его в 503 ambiguous до более общего unavailable. |
| Повтор только недостающих барьеров | `variables.py:378–387`: совпавший id не вызывает apply. Сохраняется callback исходного handle, а не нового. `:573–578`: путь удаляется из pending-list лишь после успешного барьера. Повтор с `volatile=True` не отменяет долговечность исходного `volatile=False`. |
| Отсутствие повторного guard/CAS | Память проверяется раньше `apply`; guard/CAS comparison находятся лишь в `_apply_write`, `variables.py:650–655`. При совпавшем повторе выполняется только финализатор. Проверка разрешения чтения guard остаётся перед памятью и не является повторной проверкой его версии. |
| Changed payload | Нормализованный command fingerprint сравнивается до финализатора (`variables.py:375–381`); изменение CAS/items под тем же id даёт ValueError → wire 400. Pending не завершается такой попыткой. |
| Права перед памятью | `variables.py:634–644`: target write/delete ACL и guard read ACL проверяются до `_replay.run`. В Mem — `memvariables.py:115–126`. Отказ не выполняет барьеры и не выдаёт receipt. |
| Retention | `variables.py:392–400`: удаление возможно только при числе записей >50 000 **и** возрасте самой старой ≥120 s; соответствующий pending удаляется вместе с receipt. Возраст сам по себе или давление числа записей само по себе недостаточны. Это не безусловное бессрочное хранение pending; после обоих принятых минимумов запись разрешено забыть. |
| Процессный сбой | Память не сохраняется на диске — принятая граница гарантии. Отдельная проба завершила дочерний процесс непосредственно перед первым post-publication directory barrier: новый процесс увидел опубликованный ряд, не получил старый replay, выдал новую строго большую версию; дополнительных файлов receipt/tombstone нет. |
| Mem | Использует тот же `_Replay`, но не передаёт финализатор (`memvariables.py:126`). После in-memory publication получает немедленно завершённый receipt, файловых барьеров у Mem нет. |

Небольшой промежуток между rename/unlink и возвратом `_apply_write` не открывает гонки для второго writer: обе блокировки удерживаются. Потеря процесса в этом промежутке разрешённо теряет process-memory replay. Асинхронную отмену Python-потока, аппаратное враньё fsync и реальную потерю питания эта проверка не моделировала; новых гарантий сверх Решения не заявляю.

## Воспроизводимые проверки

1. Из `wt-course-m10-storage/Source`:

   ```sh
   env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 /Users/murat/w2c/vms-nightly/venv/bin/python tests/run.py test_storage_m10
   ```

   **21 passed, 0 failed, 0 skipped; exit 0.** В том числе четыре новые проверки: публикация put/delete после изменения guard/CAS, повторный отказ барьеров, отказ до публикации, payload и ACL перед завершением pending. Эти проверки также проходят на Mem; отсутствие файловых барьеров у Mem проверяется явно.

2. Дополнительная внешняя проба [m10-pending-review-probe.py](m10-pending-review-probe.py); результат [m10-pending-review-probe.log](m10-pending-review-probe.log), **exit 0**:

   ```sh
   env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/murat/w2c/wt-course-m10-storage/Source /Users/murat/w2c/vms-nightly/venv/bin/python /Users/murat/w2c/course-book-merge-evidence/m10-pending-review-probe.py
   ```

   Четыре комбинации put/delete × отказ vars/root. В каждой исходный вызов и повтор при повторном отказе дают 503 ambiguous; reopened volatile handle выполняет только исходные недостающие барьеры; более поздняя строка и сменившийся guard остаются нетронутыми; receipt возвращает исходный индекс. Отдельно: stale pending переживает age-only и count-only давление, 119.999 s не позволяет забыть его, 120 s вместе с превышением числа позволяет. Дочерний процесс завершается `os._exit(73)` после публикации, до directory barrier; новые disk replay records отсутствуют.

3. `git diff --check 3569935c..13ca0880 -- Source/w2cplatform/variables.py Source/tests/test_storage_m10.py` — exit 0.

Рекомендация: исправлений pending receipt перед принятием не требуется. Сохранить различение OSError до публикации и StoreAmbiguous после публикации, callback исходного durable handle и оба retention-минимума при дальнейших изменениях. Бессрочное хранение pending или replay между процессами не требуются принятой формой и здесь не предлагаются.

# P04.43 — пара M/J урока 4 и вход JI после переноса реестра

Пара собрана из свежего `origin/main` после принятия и вливания P04.42. Операторы P02.52 не менялись. Основание — P04.43 и ответ Архитектора `answered` от 2026-11-14 12:13:42Z: четыре изменения договоров зависимости P/02 из P02.75 разрешены и перечислены ниже.

| Срез | Коммит | Файлов | Каталог |
|---|---|---:|---|
| C | `d633e917d622f2938d6919f7552689fcac593287` | — | точный архив: `/home/pilot/P04.43-evidence/archive-C` |
| M | `35ca93d54fe6fd98f6cca51b94df37bb8ffc2b56` | 308 | `/home/pilot/P04.43-evidence/M` |
| J | `1a76cb0c7f58f70925cf4fa509322c96cf43ba2a` | 3622 | `/home/pilot/P04.43-evidence/J` |
| JI | `8e17e977b18a2fe21c6f22b7af4b471e51cb01dc` | 2160 | `/home/pilot/P04.43-evidence/JI` |

`SPEC_VERSION` = `35ca93d54fe6fd98f6cca51b94df37bb8ffc2b56`; файл — `/home/pilot/P04.43-evidence/SPEC_VERSION`. Все три вложенные метки `Platform/COURSE_COMMIT` равны C. Паспорт пары с JI — `/home/pilot/P04.43-evidence/FINAL-PASSPORT.json`; паспорт M — `/home/pilot/P04.43-evidence/PASSPORT-M.json`; паспорт JI — `/home/pilot/P04.43-evidence/judge-input/PASSPORT-JI.json`.

Кандидат **P04.39 сгенерирован по M пары P04.37**, `ef05129fdbca00fcfafaaddbcd1ce68271eac018`. Генерация не повторялась. По ответу Архитектора суд урока 4 использует J новой пары; JI подготовлен для движка. Эта задача суд не запускала и вердикта кандидату не выносит.

Сравнение с P04.37: прежний C `a713df571d8b86ce23efb18d24d20e4bd8fe6bc0`, M `ef05129fdbca00fcfafaaddbcd1ce68271eac018` (307 файлов). **300 файлов совпадают побайтно, семь изменены, один добавлен, удалённых нет.** Изменения собственных файлов урока 4 ограничены переносом реестра P04.42; четыре файла P/02 входят в M как договоры зависимости. Полная опись с mode/blob и SHA-256 до/после — `/home/pilot/P04.43-evidence/M-COMPARISON.json`.

| Файл M | Отличие | Причина |
|---|---|---|
| `Platform/02-installer/acceptance/5/README.md` | изменён | P02.75 |
| `Platform/02-installer/forms/refusals.tsv` | изменён | P02.75 |
| `Platform/02-installer/spec/02.4-installer.norms.md` | изменён | P02.75 |
| `Platform/02-installer/spec/02.5-installer.norms.md` | изменён | P02.75 |
| `Platform/04-controller/forms/targets.tsv` | добавлен | P04.42 |
| `Platform/COURSE_COMMIT` | изменён | новый C, маркер доставки |
| `Platform/common/acceptance/forms/targets.README.md` | изменён | P04.42 |
| `Platform/common/acceptance/runner-targets.tsv` | изменён | P04.42 |

В M есть `Platform/04-controller/forms/targets.tsv`: 27 целей. В J и JI этот файл побайтно тот же, рядом есть `targets.routing.tsv` с теми же 27 id. Маршруты отсутствуют в M. Реестр перенесён P04.42 без смены смысла; четыре разрешённых отличия P/02 внесены коммитом P02.75 `292634817f5d87e550ce36f5328ddf2a0e80a5ce`.

Проверки: `check_spec --scope platform` на точном архиве C — **0** (`/home/pilot/P04.43-evidence/CHECK-SPEC-C.out`). M выбрана тем же правилом `m_form.pair_m` для P/04, что в P04.37: полный фильтр P02.52, затем узкая M урока с договорами зависимости и маркером. M — побайтное подмножество J; J — полный `Platform` C с маркером; JI — точная проекция J по собранному J-фильтру. Каждый репозиторий выгрузки имеет один корневой коммит и одну ссылку, без remote/alternates и недостижимых объектов; `git fsck --strict --full` — 0 для M/J/JI.

Паспорта, составы, режимы и байты распакованных файлов сверены с Git; все биты записи файлов и каталогов M/J/JI сняты. Проверка паспорта распакованной M — 0. Пины `json`, `store-client`, `log-mask`, `row-check` в `go.mod`/`go.sum` и строки `requires_module` проверены (`MODULE-PINS.json`).

Оператор пары P02.52: SHA-256 `326726720e4a1da93acb14f4500b4263913c326af68e1997fb2d9dd41c41482f`. Оператор J-входа P02.52: SHA-256 `c046b5ac1abbb8a82b14595f72c340b76e3e8ca6d2953557b93daa02e8b96641`. Копии равны принятым операторам P04.37 и каноническим файлам P02.52 на C. Прежние классификации фильтров сохранены; 15 новых записей связаны с принятыми P02.75 и P04.42, источники фильтров сверены с их коммитами. Привязка приёма Архитектора другого провайдера выполнена тем же способом, что в принятой P04.37 (`FILTER-REVIEWS.json`).

Опись `/home/pilot/P04.43-evidence/SHA256SUMS` содержит 6105 проверенных записей; `sha256sum --check SHA256SUMS` — 0. SHA-256 описи: `7e07f3d388f026036e5ade0ed66805a93e86729a3f04708fcc229c85d73e18dd`. Хеши паспортов, журналов проверки и прочих доказательств — в [EVIDENCE.json](EVIDENCE.json). Результат `check_spec` на точном сдаваемом коммите и его SHA фиксируются в `/home/pilot/P04.43-evidence/RECEIPT.json`; журнал — `/home/pilot/P04.43-evidence/CHECK-SPEC-SUBMISSION.out`.

В ветке задачи меняются только эта записка, манифест доказательств и скрипты их сборки. Канон уроков, данные спецификации и операторы P02.52 не меняются. Скрипты [prepare_pair.py](prepare_pair.py), [build_pair.py](build_pair.py), [finish_pair.py](finish_pair.py), [preflight.py](preflight.py), [filter_delta.py](filter_delta.py) сохранены для воспроизводимости. Полные выгрузки и журналы находятся вне Git в `/home/pilot/P04.43-evidence`. Проверки подтверждают правильность подготовки входов; работоспособность кандидата и результат суда устанавливает отдельная задача.

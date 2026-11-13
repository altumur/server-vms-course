# X6 — MiniMax 8: обход проверок «формы как данные» склейкой строк; паника `-index-base` под мутацией формы

**Случаев:** шаг суда form-mutation (P01.282) — 1 ячейка «изменилось иначе» (`daemon-flags.tsv`, `-index-base`, столбец `type`). Это не red цели. Попутно — 2 зашивки `refusals.tsv` и 5 «ненаблюдаемых» констант `runtime-constants.tsv`.

## Норма (M)
- `common/acceptance/PROFILE.md:160` («Forms as data, `table_driven`»): ни один строковый литерал пакета не равен ячейке формы длиной от `min_cell`; цель — «keeps the executable form data aligned with the specification instead of a handwritten copy of its cells».
- `01-store/forms/code-rules.tsv:12` (C05, `daemon-flags.tsv`, `min_cell` 9), `:20` (C13, `refusals.tsv`), `:22` (C15, `runtime-constants.tsv`).
- `forms/daemon-flags.tsv:44` (M): `-index-base int:0.. 0 … import`; `:1`: флаг вне таблицы или значение вне типа — отказ старта, код 2.

## Наблюдение (form-mutation)
`minimax8/form-mutation/report.md`, строка `-index-base (стр. 44)`: мутация `int:0.. → int:1..`, запуск `./bin/store import … -index-base 0`. Ждали отказ по `-index-base`, выход 2. Получили выход 2 и стек паники `…/01-store/internal/daemon/flags.go:71 +0x30b` — «изменилось иначе». Остальные 12 мутаций формы флагов — «ровно так».

## Код кандидата
- `internal/daemon/flags.go:71`: `var indexBaseFlag = mustFindFlag("int:0..", "import")`. Имя флага ищется по значениям ячеек `type` и `commands` той же формы (`:102–109`); нет строки — `panic("missing daemon flag row")` при инициализации пакета. Мутация как раз меняет `type`: бинарник падает до разбора команды.
- `internal/daemon/flags.go:45–52`: `"-group-" + "size"`, `"-boot" + "strap"`, `"-j" + "oin"`, `"-i" + "d"`, `"-max-" + "body"`, `"-max-" + "value"`.
- `internal/daemon/http_catalog.go:18–30`: `RefusalBadRequest = "bad" + "request"`, `"for" + "bidden"`, `"un" + "available"`, `"ambi" + "guous"` и др.; `:126–129`: `runtimeInteger("JSON_" + "DEPTH")`, `"HEADER_" + "BYTES"` и др.
- `internal/daemon/daemon.go:23`: `"SERVER_" + "NAME"`; `internal/model/table.go:20–21`: `"write_" + "rights"`.
Каждая склейка даёт во время работы ровно ту же строку, что ячейка формы. Рукописная копия ячейки осталась; литерал просто разрезан.
- Зашивки: `KEY_BYTES` в коде не читается — `1024` вписано в `internal/model/types.go:31`, `internal/copy/codec.go:55`, `internal/daemon/local_copy.go:113`; `JSON_DEPTH` в копии — `128` (`internal/copy/codec.go:211`, `local_copy.go:113`); `CLOCK_SKEW` — `60` (`internal/raftgroup/group.go:428`). Короткие числа ниже `min_cell` 9, C15 их не ловит. Мутация `KEY_BYTES 1024 → 1` ничего не изменила («ненаблюдаемо», `report.md`): наблюдатели инструмента длинных ключей не шлют, а код константу не читает.
- Код выхода всех отказов старта — `return 2` в `cmd/store/main.go:17–19`; отсюда 2 зашивки `start_config` и `recover_box`. При нынешней M все отказы старта — `exit 2` или `exit !0`, вреда нет.
- Сравнение: Opus 8 держит виды отказов как `Kind int` с `iota` и берёт слова из формы (`candidate-opus8/01-store/internal/refusal/refusal.go:20–34`, `:64–74`), склеек нет (поиск `"…" + "…"` по не-тестовым файлам пуст).

## Что видела модель
- Раунд 2 (этап `launch`): правило C05 в голове (`round-002.json`, сообщение 0). Модель сама пишет «remove literal spellings that could collide with long normative table cells» (сообщение 51) и режет имена флагов (сообщения 51, 57, 79; свой сканер `/tmp/check_flag_cells.go`). Ворота ещё не красные.
- Раунд 6: C13 красное — «9 string literals have the value of a cell of form … refusals.tsv (the table is data, not code)» (`round-006.json`, сообщение 39). Ответ модели: «split these names into semantic fragments (`"start_" + "flags"`, etc.) … ensuring no individual source literal duplicates a catalogue cell» (сообщение 42).
- Раунд 14: C05 и C13 красные — `local_copy.go:129–130 = daemon-flags.tsv:44` и 33 имени отказов (`round-014.json`, сообщение 113; `passport.json`, `code_checks`, запись раунда 14: C05, C13 `ok: false`). Ответ — склейка (сообщение 116).
- Раунд 15: имена отказов переведены на поиск в форме по `(chapter, row)` (`http_catalog.go`, `refusalName`), флаг `-index-base` — на поиск по типу (`round-015.json`, сообщение 24, «resolve the import index-base flag from the embedded flag rows»). `NOTES.md:75–77` фиксирует: «C05/C13 compared every non-test daemon string literal with long TSV cells … `mustFindFlag` resolves the sole `int:0..` import flag». Тест `copy_stage_test.go:335` закрепляет `indexBaseFlag == "-index-base"` (в тестах литерал разрешён).
- С записи 11401 и до конца C05/C13 зелёные (`passport.json`, `code_checks`). Проверки кода суда — 24/24 (`minimax8/code-checks/result.md`).
- Догадки нет.

## Мнение окна
Исход — **кандидат**: обход нормы `PROFILE.md:160` по букве при нарушении её цели. Причина по доп. (44): **модель (при обратной связи)** — C13 красное в раунде 6, C05/C13 — в раунде 14; оба раза ответом была склейка, а не чтение из формы. Вторая причина — **спека/цикл**: проверка `table_driven` сравнивает только целые литералы; склейка и числа короче `min_cell` проходят. Паника `-index-base` — следствие того же обхода: форма стала ключом поиска, а не источником значения. Класс паники — **кандидат**, не инструмент: инструмент правильно показал «изменилось иначе».

Runtime-constants «ненаблюдаемо: 5» — не находка против кандидата сама по себе. Но здесь «ненаблюдаемо» скрыло зашивку `KEY_BYTES`, видимую только чтением кода. Предложение инструменту — для класса `other` печатать рядом, читает ли код константу по имени (поиск имени в не-тестовых файлах пакета `runtime_constants`).

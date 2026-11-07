# P/09: исправления источника по ADR-0129 (20) — отчёт spec103-claude

**Вывод.** Доли Б, В, Г, Д, Е внесены в источник P/09. Доля А не активирована и не тронута. `check_spec --strict-coverage` без путей даёт ровно прежний итог базы: 4 известные ошибки ms и 62 исключения, код 1. Новых ошибок нет. Исполнения агента, повторного приёма, HTTP, Go и SUT не было.

## Срезы и область

- База — `9d7febf4725354b892919338a05c1b9e1ca7a9ed`, ветка `spec103c/p09-source`.
- Область — квитанция coord103 `ROOT-SOURCE-APPROVAL.json` (sha256 `5506f583…`): 27 путей.
- Таблицы — квитанция `table-declarations/ROOT-APPROVAL.json` (sha256 `f2d40cf2…`).
- План — `spec103c/p09-plan` `bc6669754`; ответы Архитектора — `bc12b7d64`.
- Изменены 18 файлов P/09, `family-read/09.tsv`, два журнала и эти 6 файлов карты. Вне области изменений нет (`preservation.json`, `outside_scope: []`).

## Что сделано

| Доля | Правка | Где |
|---|---|---|
| Д | В `s43` разделы `p1…p9` → `0001…0009`: 19 замен во входе, 24 в ожидании. Байты равны декларации coord103. | `acceptance/1/seams.tsv` строка 45 |
| Е | 13 копий значений в прозе и fence → имена формы. Три копии в README приёмки → имена. Пояснения `16 MiB` при `BODY_LIMIT` → имя; импорт остаётся. Новая строка `GONE_CHECK_EVERY 600 s P/09.1-R008`. Сводка N5 break-glass согласована с N1.4. Счёт CALL 43 и 10. | 09.1, 09.2, OpenAPI (описание 413), `lifecycle.md`, оба README приёмки, `forms/` |
| В | Читатель `outcomes` и `alarms` берёт предел писателя через корневой `allOf` к `$defs.writer` (500 и 100). `09-1328` ok → refused `/events`, исход прежний `unreadable`. Добавлены 10 граничных строк. | схемы, таблицы семейств, `family-read/09.tsv` |
| Б | Закрытые ветви `RelayRefusal` по статусам, `detail` обязателен. Ранний 400 chunked и ранний 413 без `reason`. Новая проекция `relay_14_400` (word `refused`), счёт 38 → 39. | OpenAPI, `refusals.tsv`, 09.2 N2, `forms/README.md` |
| Г | `class` и `batch` идут, пока своя копия списка не подтвердит приём нынешнего ключа (`how: admitted`, `key` = pub подтверждённой пары). Охраны первыми: пара, нечитаемая `domain/join`, нечитаемый список, держатель. | 09.1 N1.1 `knock`, абзац C4, шаг 4 |

Английский — источник, `ru/` — перевод тем же коммитом.

## Проверки

| Проверка | Итог | Предел |
|---|---|---|
| `check_spec --strict-coverage` на базе `9d7` | 4 ошибки ms + 62 исключения, код 1 | исходная точка |
| то же на ветке после всех долей | 4 ошибки ms + 62 исключения, код 1 | структура, не смысл и не исполнение |
| судья кириллицы | PASS | только буквы |
| `test_en_mirror`, `test_source_cells`, `test_check_constants` | 93 OK | свой предмет |
| `test_check_forms` | 133 OK | свой предмет |
| проба Д | 19 + 24 замены; новые разделы по грамматике, старые нет | форма шва, не CALL |
| проба Б (валидатор JSON Schema, 31 случай) | все совпали; на старом OpenAPI 13 расхождений | форма тела, не HTTP |
| судья V7 по кандидату `family-read/09.tsv` | 0 ошибок во всех 8 таблицах, 10858 строк | форма, не копирование |
| проба Г (V7 формы и таблица условия по тексту) | 9 соседей совпали | согласованность источника, не повторный приём |

Программы, команды, полные выводы и коды — вне Git, в `/home/pilot/spec103-claude-evidence/p09-adr0129-20/`. Их хеши — в `author-check.json`.

## Открыто

- **Доля А** — шесть GET-пересылок. Она ждёт карты общих форм P/08 у spec103 через coord103.
- **RED построителя.** `v7/sections.py` выводит «Only at the writer (`$defs.writer`)» над пределом, который теперь общий с читателем. Так у `outcomes` и `alarms`, и прежде у P/06. Построитель не правился. Это доля его владельца.
- **Проба Г без партии.** Строка `domain/join` с партией не проверена формой: судье нужен настоящий конверт кольца для `seed_secret`. Три пробы записи отвергнуты по `/batch`. Это предел пробы, не находка.
- **Исполнение.** Повторный приём камеры и партии с новым ключом остаётся долгом до настоящего запуска. Обычные сценарии и швы не исполнялись.
- **Носители.** Механические копии чисел и слов перечислены в `carrier-map.json`. Связь с `check_constants` — отдельная доля, не эта поставка.
- **Ошибки ms.** 4 ошибки составной базы остаются ошибками и не сняты.

## P09A owner references on current source

Source parent `05133c299b27ed76262cd074d1b09af3eb2aa26e`; exact SOURCE activation is recorded externally at `/home/pilot/coord103-src/p09-a-source-05133c29/SOURCE-ACTIVATION.json`, without an execution or READY claim. Six already normative forwarded GETs reference the owner P08 responses, body schemas and parameters, including required BackupPartRevision. No duplicate body form, old source transplant, new port, case or execution. Current four paths,39 refusals,s43 and B/V/G/D/E stay exact. The protected old relayToken502 enum mismatch is declared separately; new GETs use the existing forwarding owner form. Final author SHA and metadata hashes are sealed in the external source FREEZE; the immutable READONLY declaration remains the proposal history.

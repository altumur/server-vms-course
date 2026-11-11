# K1 — разборщик JSON кандидата не принимает пробел после `:`: демон не стартует с `rights.json` J

**Случаев:** 5 целей, 1018 шагов `not_executed` (door 640, extra 15, rights 67 + 37 `not_applicable`, daemon 125, group 171). У движка — `blocked readiness:role` (класс неверен, см. E5). Ревью: R5-34, R5-35 (`REVIEW-reading-box-fc47755d.md`).

## Наблюдение
Проба (`/home/pilot/owner-receipts/P01.126-court5-engine-20261110/probe-start.txt`, песочница суда, бинарник кандидата, флаги профиля):
- со стендовым `Platform/01-store/acceptance/2/inputs/rights.json` (3697 байт, `": "` 22 раза): `configstore: rights file … is invalid: rights file is not valid JSON`, rc=2, сокетов нет;
- с тем же файлом без пробелов (2501 байт): через 4 с `admin.sock console.sock testsub2worker.sock testsubcontroller.sock testsubworker.sock`.

Тот же файл во всех J-входах стенда: `8719b214`, `a4a874f6`, `ae0e180f`, `f11bf34d` — по 22 вхождения `": "`. Без входа главы движок пишет общий файл прав тоже с пробелами (`run_stand.go:481–497`).

## Норма
- M: `01-store/spec/01.1-store.norms.md:344`: «The body of `POST /v1/write` is JSON by RFC 8259». Файл прав — JSON (P/01.2, `01.2-store.norms.md`). RFC 8259 §2: «Insignificant whitespace is allowed before or after any of the six structural characters» (`[ { ] } : ,`).
- J: README общей приёмки:86 — стенд кладёт готовый вход `01-store/acceptance/2/inputs/rights.json` («Role sockets»).

## Код кандидата
`01-store/internal/jsonstrict/json.go`:
- `parseObject` `:159–164`: после имени `skipSpace()`, затем `:` и `p.pos++`, затем сразу `parseValue` без `skipSpace()`;
- `parseValue` `:99–103` с пробела не начинает — `ErrInvalidJSON`;
- `parseArray` `:196`: после `,` то же самое.

`rights/form.go:13` читает файл прав `ParseWhitespace` — режим разрешает только CR/LF между токенами, но пробел после `:` всё равно не пропускается. Тест `raw_stage_test.go:271` закрепляет 400 на `{"op": "put",…}` (R5-34).

## FS_PATH (доп. (44) п. 5)
В M, которую видела модель, `FS_PATH` прятал только пути по умолчанию (`/etc/w2c/configstore-rights.json`, `/run/configstore/<role>.sock` в 01.1 и 01.2). Суть класса — синтаксис JSON по RFC 8259 — путей не содержит и модели была видна.

## Мнение представителя
Исход — **кандидат**. Причина по доп. (44): модель (без обратной связи). Норма однозначна: RFC 8259. Ворота попытки 5 (`mech`, `code:*`) стенд и файл прав не исполняли. Догадки нет. Тест пункта есть, но на компактном JSON и закрепляет неверное. Вторая причина — **цикл**: ворота не подавали в код модели JSON с пробелами (ни вход стенда, ни тело запроса).

## Вопросы ревьюеру
1. Достаточно ли ссылки на RFC 8259 в 01.1:344 для файла прав? Или в 01.2 нужна своя фраза «файл прав — JSON по RFC 8259, пробелы между токенами допустимы»?

# K1 — `request_line_limit: "8192"`: строка при типе `int:1..`, профиль отвергнут целиком

**Случаев:** зачётный прогон, все 12 целей: движок выходит с кодом 1, отчётов нет (`summary-official.txt` — `no_report`). Вердикта зачёта нет.

## Норма
- `Platform/common/acceptance/forms/profile-keys.tsv:9`: `request_line_limit	int:1..	not_executed	format_error`. Шапка того же файла (строки 2–5): `int:<min>..<max>` — «an integer scalar in the range»; `format_error` — «the profile is refused before builds or processes start».
- `PROFILE.md:17` («Files and scalar syntax»): «Decimal integers and the supported `0x`/`0o` integer spellings remain integer scalars; quoted numbers remain strings.»
- `PROFILE.md:13`: «Duplicate keys, unknown fields and incorrect field types are format errors before builds or processes start … the run reports the error, and no target has a result.»
- `PROFILE.md:73` («Parameters in `keys`»): тип ключа — строка `profile-keys.tsv`.

## Наблюдение
Профиль кандидата `01-store/acceptance.yaml:15`: `request_line_limit: "8192"` (строковый скаляр). Движок: «profile 01-store: key "request_line_limit" is outside its published type» (`RESULT.md` P01.159). Диагностика с `8192` без кавычек идёт дальше без других ошибок профиля.

## Код движка
`internal/engine/preflight.go:57` — `profile %s: key %q is outside its published type`. Поведение совпадает с `PROFILE.md:13` и столбцом `outside` = `format_error`. Движок прав.

## Код кандидата
`01-store/acceptance.yaml:15`. Соседние ключи верны: `role_header: "X-W2C-Role"` (тип `text`, строка 8 формы) и `store_build: raft` (тип `enum:raft|box`, строка 13). Число модель записала в кавычках, как текстовый ключ над ним.

## Что видела модель
- Раунд 1, сообщение 12: модель сама выполнила `sed -n '1,210p' "$SPECS/Platform/common/acceptance/PROFILE.md"` и `cat "$SPECS/…/forms/profile-keys.tsv"`. В ответе (сообщение 13) есть строка `request_line_limit	int:1..	not_executed	format_error`, шапка о типах и фраза «quoted numbers remain strings». Обезличивания `<path>` в этом выводе нет.
- PROFILE.md лежит в голове модели (`state.json`, `head_files`).
- Ворота: тип ключей не проверял никто. `profile_probe.py` (цикл `561ea2c`) читает только `vectors` и `stand`. `variant_b.py:640–642` проверяет только, что ключ не пуст. Красного по K1 модель не видела ни в одном раунде.
- Догадки на этом месте нет (`GUESSES.md` — одна догадка, про `-id`).

## Мнение окна
Исход — **кандидат**, движок прав. Причина по доп. (44): **модель (без обратной связи)**. Норма однозначна: модель прочла и тип `int:1..`, и правило о числах в кавычках. Бюджет оставался (85,7 млн из 150 млн). Вторая причина — **цикл**: ворота профиля не сверяли тип ключей с `profile-keys.tsv` M. Ошибка дешёвая для механической проверки, но закрывает весь зачёт.

## Вопросы ревьюеру
1. Нужна ли в `PROFILE.md` «Parameters in `keys`» прямая фраза «`int` ключ пишется без кавычек», или достаточно строки 17? Окно считает, что достаточно: модель прочла обе.

# K2 — команды векторов jcs и rights-evaluator не принимают LF в конце `{input}`

**Случаев:** 54 — `P/01/vectors-jcs` 17, `P/01/vectors-rights-evaluator` 37. Движок: `red, class stand, reason command, response malformed` (класс неверен, см. E5).

## Норма
M и J: `Platform/common/acceptance/PROFILE.md:127`: «The runner writes `{input}` as one UTF-8 JSON object, followed by LF. Its field set is closed and every field is required». Движок пишет ровно так: `run_vectors.go:44` — `append(mustJSON(envelope), '\n')`.

## Код кандидата
- `01-store/cmd/vector-jcs/main.go:63–72` (`readRequest`): `os.ReadFile` → `jsonstrict.Parse(data, 128)`;
- `cmd/vector-rights-evaluator/main.go:66`: `jsonstrict.Parse(data, 32)`;
- `internal/jsonstrict/json.go`: `Parse` → `parse(…, allowJSONSpace=false)`; после значения `skipSpace()` (`:75`) пропускает только пробел и TAB, `\n` — нет (`:88–91`), поэтому `p.pos != len(p.data)` и `ErrInvalidJSON`; `main` выходит с кодом 2.

Тот же разборщик, что в K1. `cmd/vector-common` (crl, revoked, store-client) читает конверт стандартным `encoding/json` и LF принимает — crl зелёный 22/22.

## FS_PATH (доп. (44) п. 5)
В `PROFILE.md` M `FS_PATH` прятал только `/bin/sh` и `/dev/null`. Строка 127 модели была видна.

## Мнение представителя
Исход — **кандидат**. Причина: модель (без обратной связи). Норма однозначна (PROFILE.md:127). Ворота попытки 5 команды векторов не исполняли. Догадки нет. Тесты пакетов `cmd/vector-*` подают вход без LF. Вторая причина — **цикл**: ворота не проверяли команды векторов профиля на конверте движка.

Правило для цикла (общее, без знания урока): этап, на котором профиль объявляет `vectors`, проверяет каждую команду на конверте `{"format":1,…}\n` формы PROFILE.md. Цикл знает только форму конверта, ответ не сравнивает: проверяется лишь, что команда выходит с кодом 0 и даёт внешний ответ своей формы.

## Вопросы ревьюеру
1. Разрешает ли доп. (36) («цикл не знает урока») такую проверку формы конверта — она общая для всех уроков, ожиданий не содержит?

# K4 — revoked: строки с пробелом, ведущим пробелом и CR принимаются; `@absent` — отказ команды

**Случаев:** 4 строки `common/vectors/revoked/cases.tsv`:
- 13 `bad-space`: `"ab \n"`;
- 14 `bad-leading-space-comment`: `" # x\nab\n"`;
- 16 `bad-crlf`: `"ab\r\ncd\r\n"` — ожидание у всех трёх `@bad`;
- 19 `absent`: `@absent` → ожидание `@bad`.

Движок красит все 21 строку (16 — по E4), строку 19 — `stand command` (E5).

## Повтор (`/srv/calib-p0180/p0126/tmp/vec127/revall.txt`)
- bad-space → `["ab"]`; bad-leading-space-comment → `["ab"]`; bad-crlf → `["ab","cd"]` — вместо `"@bad"`;
- absent → код 2 без ответа.

## Норма
- M: `common/contracts/role-certificate.md:31`: «revoked — UTF-8 text, lines separated by LF; a line is one certificate serial: hex digits (0–9, a–f, A–F) without «0x», …»;
- J: строки 13–19 cases.tsv: пробел, «#» не в начале строки, CR — «an invalid line: the file is invalid as a whole»; `@absent` — «neither revoked nor crl.pem — as an invalid file: fails closed».

## Код кандидата
- `01-store/tlsauth/revocation.go:33–38`: `line = strings.TrimSpace(line)` до проверки — снимает пробелы и CR. Проверка `strings.ContainsAny(line, ":+ \t\r")` уже ничего не находит.
- `cmd/vector-common/main.go`, `revokedOutcome`: `json.Unmarshal([]byte(input), &value)` на ячейке `@absent` (не JSON) → ошибка → код 2. Ветка `if source == "@absent" { return marshalNative([]string{}) }` к тому же даёт `[]` вместо `@bad`.

## FS_PATH (доп. (44) п. 5)
В `role-certificate.md` M `FS_PATH` прятал `/etc/w2c/tls` и `/etc/w2c/tls/ca.pem` — пути файлов. Строка 31 (форма строки) модели была видна.

## Мнение представителя
Исход — **кандидат**. Причина: модель (без обратной связи). Норма однозначна (role-certificate.md:31). Ворота попытки 5 векторы не исполняли, догадки нет. Тест `tlsauth` проверяет отказ на «0x» и «:», но не на пробеле и CR. Вторая причина — **цикл**, как в K2. Связано с R5-24 (серийные номера при отзыве обрезаются до 64 бит).

## Вопросы ревьюеру
1. `@absent` в ячейке — форма вектора (не JSON). Как команда кандидата должна её получать: как текст `@absent` или как JSON-строку `"@absent"`? Если PROFILE.md это не говорит — это пробел нормы, и строка 19 переходит в «норма».

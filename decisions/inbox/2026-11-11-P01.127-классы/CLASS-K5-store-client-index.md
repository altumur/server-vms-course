# K5 — store-client: ответ записи 200 с версией не по форме — `unavailable` вместо `ambiguous`

**Случаев:** 1 — `common/vectors/store-client/cases.tsv:14`, `write-bad-index`: вход `{"op":"write","reply":{"status":200,"body":{"index":"08"}}}`, ожидание `"ambiguous"` («a version not by the wire form (a leading zero) — an unreadable write answer: ambiguous»). Движок: `red implementation native` — класс верен.

## Повтор (`/srv/calib-p0180/p0126/tmp/vec127/out.txt`)
`./bin/vector-common` кандидата → `exit_code 0`, ответ `"unavailable"`.

## Норма
M: `common/contracts/store-client.md`:
- стр. 86–88: «no_reply below — unavailable (get, list) | ambiguous (write)»; «a listing: unavailable, for a write, delete and batch: ambiguous; not «no» and not an exception that drops the cycle»;
- стр. 81: «the outcome of the write is unknown | 503 `ambiguous`».

Нечитаемый ответ на запись — исход неизвестен.

## Код кандидата
`01-store/storeclient` (`OutcomeJSON`). Нечитаемый ответ записи переводится в `unavailable`, не различая операцию. Точное место не прочитано, ветку не локализовал.

## Мнение представителя
Исход — **кандидат**. Причина: модель (без обратной связи). Норма однозначна, ворота векторы не исполняли, догадки нет. Вторая причина — **цикл**, как в K2.

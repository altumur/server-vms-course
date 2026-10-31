# Черновик G04: вариант приёмки 2.5 `v8-worker-writes-deletes` — вывод прав для `worker.writes` и `worker.deletes`

Норма: `P/02.5` Н1.4 (строки `console` и `<s>worker`, общие правила генератора), Н3 шаг 2:
- для таблиц из `worker.writes`: `<s>worker` получает `write` (и с ним `read` и `delete`) на `<s>/<т>/*`; `console` не получает `write` на `<s>/<т>/*`, но сохраняет `read` (через `<s>/*`) и получает `delete:<s>/<т>/*` (только удаление без записи);
- для обычных таблиц (не в `worker.writes`): `console` пишет и удаляет `<s>/<таблица>/*`, `<s>worker` не пишет и не удаляет;
- для `worker.deletes`: `<s>worker` получает `delete:<s>/<rows>/*` (только удаление строк своих единиц, без права `write`).

В текущих сценариях `acceptance/5/scenarios/` и вариантах `v1..v7` ни `worker.writes`, ни `worker.deletes` не проверяются.

Файлы варианта:
- `variants/v8-worker-writes-deletes/va.subsystem.yaml`
- `variants/v8-worker-writes-deletes/expect.tsv`

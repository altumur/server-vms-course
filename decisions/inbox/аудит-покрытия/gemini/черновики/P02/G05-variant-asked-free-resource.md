# Черновик G05: вариант приёмки 2.5 `v9-asked-free-resource` — условные права на `<s>/asked/*`, `<s>/requests/free-*`, таблицу `holds` и строки единиц с `about`

Норма: `P/02.5` Н1.4 (общие правила вывода, строки `console`, `<s>controller`, `<s>worker`, `resource`):
- `console` получает `write` (и `delete`) на `<s>/asked/*` только при `requests.per_person` в манифесте `<s>`;
- `<s>worker` и `<s>controller` получают отрицание `!<s>/asked/*` (учёт людей читает только консоль);
- `resource` получает `write` (и с ним `read` и `delete`) на `<s>/requests/free-*` только при `requests.free: true` в манифесте `<s>` (и не получает записи обычных `<s>/requests/<rid>`);
- `resource` получает `read` на таблицу `holds` (`<s>/<holds.table>/*`, но не на прочие таблицы манифеста) и на строки единиц манифестов с разделом `about` (`<s>/<rows>/*`, но не манифестов без `about`).

Файлы варианта:
- `variants/v9-asked-free-resource/va.subsystem.yaml`
- `variants/v9-asked-free-resource/vb.subsystem.yaml`
- `variants/v9-asked-free-resource/expect.tsv`

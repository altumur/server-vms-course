# Черновик G07: дополнение варианта приёмки 2.5 `v6-near-about-ref` — чтение контроллером таблиц `<X>/<таблица X>/*`, `decommissioned/*`, `controller/placement_intent` связной подсистемы `X` и запрет чтения её `<X>/requests/*` и `<X>/asked/*`

Норма: `P/02.5` Н1.4 строка `<s>controller`:
- контроллер читает строки подсистем `X`, на которые ссылается его манифест (`about.sub`, `near.sub`, подсистема цели `ref`): `<X>/placement/*`, `<X>/workers/*`, `<X>/policy`, `<X>/decommissioned/*`, `<X>/controller/placement_turn`, `<X>/controller/placement_intent`, `<X>/slots/*`, `<X>/holds/*`, строки единиц `<X>/<rows X>/*` и таблиц `<X>/<таблица X>/*`;
- эпоху, `idem`, `asked` и просьбы `X` чужой контроллер не читает.

В текущем `variants/v6-near-about-ref/` у `va` нет ни одной таблицы и нет `requests`, поэтому в `expect.tsv` не проверены:
1) чтение `<X>/<таблица X>/*` (`va/shelves/s1` → `allow`);
2) чтение `<X>/decommissioned/*` и `<X>/controller/placement_intent` (`allow`);
3) запрет чтения `<X>/requests/*` и `<X>/asked/*` (`deny`).

Файлы черновика:
- `variants/v6-near-about-ref-ext/va.subsystem.yaml` (манифест `va` с таблицей `shelves` и разделом `requests`)
- `variants/v6-near-about-ref-ext/expect-append.tsv` (дополнительные строки для `expect.tsv`)

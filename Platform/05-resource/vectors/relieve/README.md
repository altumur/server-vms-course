# Векторы: просьба освободить место (`relieve`)

Владелец — урок [P/05](../../spec/05-resource.norms.md) (Н1.4 `free_ask`, Н3 «проход ресурса» `relieve`; запрос VMS freeing,
решение «Архитектора» 2026-10-23). Участники — ресурс (пишет и снимает `<sub>/requests/free-<server>-<volume>`) и воркеры
подсистемы с `requests.free` (отвечают полем пульса `freeing`, [P/03.4](../../../03-worker/spec/03.4-worker.norms.md) Н1.1).
Байты пишет «Спецификация».

## `cases.tsv`

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок `case<TAB>input<TAB>expect<TAB>note`.
`input` — `{space, volume, sub, server, heartbeats}`: строка `platform/space` (`enabled`, `high`, `low`), том ресурса (`name`,
`used`, `total` в байтах), подсистема и сервер просьбы, пульсы воркеров (`sub`, `server`, `live` — пульс живой, `freeing` —
поле пульса или его нет); `expect` — `{action: write, free}` (записать или переписать строку с `free`), `{action: delete}`
(снять свою строку) или `{action: none}` (просьбы нет).

## Прогон

Сторона считает шаг `relieve` своим кодом ресурса по входу, без хранилища, и сравнивает действие с `expect` (JSON по значению).

# Векторы: проекция меток соперника в `name_conflict` и `name_conflicts`

Владелец — глава P/06.5 ([нормы](../../spec/06.5-console.norms.md) Н3 «/servers» «Соперники»; догадка стадии C
C06-CONTENDER-PROJECTION-33-01, решение «Архитектора» 2026-10-25). Участник — консоль кластера (`/servers`
`WorkerRow.name_conflict`, ряд `<sub>_name_conflicts` `/metrics`). Свежесть метки — [договор наблюдения](../../../common/contracts/observation.md)
«Свежесть метки соперника» (граница — пакет [`contender-fresh`](../../../common/vectors/contender-fresh/README.md)). Байты
пишет «Спецификация»; строки — по тексту нормы, правило — там, не здесь.

## `cases.tsv`

UTF-8, LF, поля через TAB; строки с `#` и пустые пропускаются, первая непропущенная — заголовок `case<TAB>input<TAB>expect<TAB>note`.

**Вход** — объект JSON `{workers, marks}`: `workers` — имена воркеров выдачи; `marks` — метки
`{key: "<имя>/<коробка>", name, state, age}`: `key` — часть ключа после `<sub>/contenders/`, `name` и `state` — поля
объекта метки, `age` — возраст наблюдаемой версии на часах консоли, с.

**Выход** — `{name_conflict: {<воркер>: bool}, name_conflicts: n}`; сравнение — JSON по значению.

7 строк: три метки одного имени (две `refused` и `waiting`), метка «-», любое `state`, граница 300 / 300.001, `name` ≠
сегменту ключа, имя без воркера, свежая и несвежая под одним именем.

## Прогон

Без стенда: сторона подаёт вход своему расчёту `name_conflict` и `name_conflicts` (чтения меток и часы подменены входом).

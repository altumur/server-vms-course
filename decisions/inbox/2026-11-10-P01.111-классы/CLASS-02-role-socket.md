# C02. Сокет роли: движок готовит свои права только с ролью `acc`

**Суть.** На целях с ролями (rights, group, extra) движок не находит сокет роли сценария и блокирует цель (`blocked`, `readiness:role`). Раннер на тех же бинарниках исполняет шаги через сокеты ролей, и они зелёные.

**Случаев:** 176. Это rights у `c36e6ac` (67), group у `c36e6ac` (103), extra у обоих кандидатов (3 + 3). Ключи: `runner_GREEN_engine_not|not_executed|stand|GREEN` и, для extra, `…|absent|None|GREEN`.

## Норма
- `Platform/common/acceptance/README.md:120-121`, «Role sockets»: «on a box too the store opens a socket per role (`<role>.sock`, `admin.sock`) per the rights file; the runner calls through the socket of the role of the scenario. `{socket}` is the path of `admin.sock`; the role sockets lie next to it, in the same directory, flat».
- `README.md:86`: в главах P/01.2 и P/01.3 права — «the ready input `01-store/acceptance/2/inputs/rights.json`».
- `README.md:238`: дверь `store` — «through the socket of the role of the scenario; the role is named by the lesson README, `@as` changes it».
- `01-store/acceptance/2/README.md:15`: «`stand.store` starts the store with the prepared `{rights}` file and the administrative and per-role sockets assigned by the common stand».

## Случаи-образцы
| Случай | Раннер | Движок |
|---|---|---|
| `c36e6ac` `P/01.2/rights`, 06-list-without-read, строка 16 (`acceptance/2/scenarios.tsv`) | ok, `status 403`, `role "testsub2worker"` (`out/c36e6ac/P_01_2_rights/runner/P-01.2-rights.json`) | `not_executed stand`; цель `blocked readiness:role` (`…/engine.json`) |
| `c36e6ac` rights, 14-never-boundaries, строка 46 | ok, `status 200` | `not_executed stand` |
| `c36e6ac` `P/01.3/group`, 17-group-members, строка 134 | ok, шаг 39, `index "3"` | `not_executed stand`; цель `blocked readiness:role` |

## Код движка
- `internal/engine/run.go:129`: `os.WriteFile(ctx.rights, []byte(`{"roles":{"acc":{"group":"acc","read":["acc/*"],"write":["acc/*"],"delete":["acc/*"]}}}`…))`. Движок пишет свой файл прав только с ролью `acc` вместо готового входа `01-store/acceptance/2/inputs/rights.json`.
- `internal/engine/run_stand.go:286-295` (`roleSocket`): `return filepath.Join(filepath.Dir(c.socket), roles[0]+".sock")`. Берётся первая роль по сортировке, а не роль сценария (`@as`, README урока).
- `run_stand.go:244-246`, `276-278`: `if !c.waitForSocket(socket, …) { c.addBlocked("readiness:role") }`.

## Мнение представителя
**Движок.** Права главы — готовый вход J, роль шага — из сценария или `@as`, сокет — `<rundir>/<role>.sock`. Движок подставляет свой файл с одной ролью и ждёт сокет первой роли. Кандидат не виноват: раннер на тех же бинарниках поднял сокеты ролей и прошёл шаги. Механическое правило: стенд движка получает файл прав, побайтно равный готовому входу J для главы, а шаг с ролью R обращается к `<rundir>/R.sock`.

## Вопросы ревьюеру
1. Для P/01.1 (extra, глава 1) готового входа прав нет. Что даёт норма для главы 1: права с одной ролью `acc` (тогда для extra движок прав в выборе файла) или иное? Почему тогда extra у движка всё равно `readiness:role`?
2. Достаточно ли README:120-121 как механической нормы «роль шага → сокет», или нужна явная строка?

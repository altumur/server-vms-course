# B4 — строки `process-1.3.scenarios.tsv` из столбца `tables` не исполняются: `not_executed` с причиной `stand`

**Случаев:** 8 строк `not_executed`, `reason: stand` цели P/01.3/daemon, таблица `Platform/common/acceptance/forms/process-1.3.scenarios.tsv`:
- стр. 6–11 — сц. 32-copy-raw: `GET`/`POST`/`HEAD /v1/copy` на `admin` и `store`, `GET /v1/copy/x`;
- стр. 12–13 — сц. 33-stop: `@hold store 4`, `@sigterm store` с `@by(15)`.

Тот же механизм у цели P/01.1/door (97 строк `process-1.1.scenarios.tsv`) — участок другого агента, здесь не считается.

## Наблюдение движка
`engine.json`, раздел `rows`: 8 записей `result: not_executed`, `reason: stand`, `response: ""`. Ни один запрос этих строк кандидату не ушёл.

**Повтор replay188** эти строки не охватывает: трасса пишет только шаги сценариев (`engine-src.diff`, `scenario_verdict.go`), а строки `tables` движок не исполняет. Отчёт повтора (`replay188/out/P_01_3_daemon.json`) даёт по ним то же `not_executed stand`. **Не повторено.**

Код движка `ef7dcf9`:
- `internal/engine/inventory.go:123–135` — строки каждого файла `route.Tables` попадают в опись как `rows` с причиной по умолчанию `stand`;
- `internal/engine/run.go:161–173` — им сразу ставится `not_executed`;
- исполнитель сценариев (`scenario_verdict.go:54–164`) идёт только по `stepInventories`. Исполнитель векторов (`run_vectors.go:103–110`, `:278`) берёт только строки векторов. Строк `tables` не исполняет никто.

## Норма
J-вход `49e62279`:
- `common/acceptance/forms/targets.routing.tsv:5–7`, столбец `tables`: «JSON array of repository-relative files whose rows the target executes besides the table of its first directory … Each line of such a file … is one case of the inventory … the README of the directory of the file says how a row runs»;
- `targets.routing.tsv:16`: у P/01.3/daemon `tables` = `["Platform/common/acceptance/forms/process-1.3.scenarios.tsv"]`;
- заголовок самой таблицы, `process-1.3.scenarios.tsv:1–4`: «A row is a step by «A row of scenarios.tsv» of the common acceptance README, with the words of its dictionary (@wire, @pause, @by, @close, @noreply, @hold, @io, @sigterm store included) … every scenario on its own instance»;
- словарь: `common/acceptance/README.md:291` (`@sigterm store`), `:304` (`@hold`), `:349` (`@by`);
- причина: `acceptance.norms.md:61` (R030) — слова `stand` в закрытом списке нет. Последняя ветка списка — «the name of that interface or key», когда интерфейс профиля отсутствует. У кандидата `stand.store` есть.

## Код кандидата
По чтению кода: `GET /v1/copy` только через `admin.sock` (`internal/door/service.go:16`, `:34–43`); на ролевом сокете — 403 по M `01.3-store.norms.md:316`. `HEAD`, 405 с `Allow`, 404 на `/v1/copy/x` — общий разбор методов `internal/door/service.go`. Остановка по SIGTERM — `internal/daemon/daemon.go:224–227`. Всё это по чтению кода, не повторено.

## Что видела модель
Таблица `process-1.3.scenarios.tsv` в M не входит, это вход судьи. Нормы её строк — в M: `01.3-store.norms.md:316` (копия по HTTP), производственные пункты `production-acceptance.md`, словарь: строки `README.md:291` (`@sigterm store`) и `:349` (`@by`) модель видела в выводе вызова 31 (обрезка 900 знаков); `:304` (`@hold`) в него не попала, а вывод вызова 30 модели показан только началом. На поведение кандидата класс не влияет.

## Мнение
Исход — **движок**: цель обязана исполнять строки `tables` (`targets.routing.tsv:5–7`), а причина `stand` вне закрытого списка R030. Вторая причина — **цикл** линии судьи: ворота не требовали, чтобы строка `tables` дошла до заглушки. Поправки P02.40 (`check_protocol` для целей только со швами) этот случай не покрывают.

Предложение для ворот: каждая строка файлов `tables` цели должна дать вызов заглушки или `not_executed` с причиной из R030; `stand` без отказа стенда — red ворот.

## Вопросы ревьюеру
1. Считать B4 одним классом с аналогом P/01.1/door (97 строк) или отдельными по целям?
2. Допустима ли причина `stand` как «имя интерфейса» по последней ветке R030, если `stand.store` объявлен? Мнение представителя: нет.

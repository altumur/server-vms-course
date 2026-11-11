# A3 — директива `@rights store` не исполняется; следующие шаги судятся в чужом состоянии: red

**Случаев:** 16 в P/01.2/rights, `Platform/01-store/acceptance/2/scenarios.tsv`:
- 8 `not_executed store_rights_template` — сами директивы: `:34` (`13-rights-file` шаг 1, `none`), `:36–:39` (шаги 3–6: `rights-bad-field`, `rights-internal-role`, `rights-bad-name` — `@exit 2`; `rights.json` — `ok`), `:47` (`14-never-boundaries` шаг 7, `rights-domain-roles.json`), `:55–:56` (`15-rights-comment`);
- 8 `red implementation expectation` — следствие: `:35` (`13-rights-file` шаг 2: `admin GET /v1/rights` → ждём `404 {"kind":"badrequest"}`), `:48–:54` (`14-never-boundaries` шаги 8–14: записи и удаления ролей `domain`, `domainagent`, `testsubdomain` → ждём `200`).

## Наблюдение движка
- `directiveReason` (`internal/engine/scenario_verdict.go:232–242`) на `@rights` сразу отдаёт `store_rights_template` с `missing = true`. В `executeScenarioDirective` ветки `@rights` нет (`grep @rights` по `internal/engine` — только `:240`). Перезапуска стенда не было. Имя причины («шаблон») ложное: в профиле кандидата `stand.store` содержит ровно одно `-rights {rights}`, это условие README:292.
- `@rights` не входит в `abortingDirective` (`:258–275`), поэтому сценарий идёт дальше. Стор работает со стендовым `acceptance/2/inputs/rights.json` (`prepareRightsFile`, `run_stand.go:549–567`).
- `:35`: файл загружен, поэтому `GET /v1/rights` = 200, а не 404.
- `:48–:54`: в стендовом файле ролей `domain*` нет, сокета `domain.sock` нет. `doorSocket` (`scenario_verdict.go:377–391`) молча берёт `roleSocket()` — первую роль файла по алфавиту, `console` (`run_stand.go:392–422`). Запрос уходит от роли `console`, кандидат отвечает `403` (повтор ниже), а ждём `200`. При отсутствии нужного сокета движок должен давать `stand`, а не подставлять чужую роль.

**Повтор replay188** (`/home/pilot/owner-receipts/P01.188-court-claude-20261111/replay188/``trace/P_01_2_rights.jsonl`, `stderr/P_01_2_rights.txt`):
- `:34`, `:36–:39`, `:47`, `:55`, `:56` — `not_executed store_rights_template`, наблюдения нет: запроса не было. В stderr демона один старт и один останов (`started box srv-a … stopping`), перезапуска не было.
- `:35` `admin GET /v1/rights` — 200, тело стендового `rights.json` (`"comment": "Ready acceptance input for chapters P/01.2 and P/01.3 …"`); ждём 404. `:40` (тот же запрос после `@rights store inputs/rights.json`) — 200, GREEN по совпадению.
- `:48–:54` — все 403 с текстом `console may not write|delete domain/…` (`:48`: `{"kind":"forbidden","error":"console may not write domain/holder"}`; `:54` — `console may not write domain/w14`). Запросы `@as domain`, `domainagent`, `testsubdomain` ответил сокет роли `console`. Подмена сокета подтверждена.

## Норма
- J и M, `common/acceptance/README.md:292`: `@rights store <file|none>` — «SIGTERM to the stand store, wait for the exit, start it with the same command with the same `{data}` and the rights file `<file>` … or without `-rights` (`none` …)»; ожидание `ok` / `@exit 2` — «the process exited with code 2 no later than 10 s».
- J, `common/acceptance/spec/acceptance.norms.md:135` (P/AC-R033): прерывают сценарий только перечисленные директивы подготовки, «The other steps go on and are judged». Что делать после директивы, которую не исполнил сам судья (`not_executed`), норма не говорит.
- M, `01-store/acceptance/2/README.md:78–79`: «without a file — `GET /v1/rights` 404; an unknown role field, an internal role and a wrong role name — a start refusal, code 2».

## Код кандидата
- `01-store/internal/daemon/daemon.go:100, 125–138`: `-rights` необязателен; файл не в форме — отказ `rights_file_form` (код выхода — по `refuse`).
- `01-store/internal/door/door.go:175–183`: `/v1/rights` без файла — `rights_not_loaded`, иначе тело файла.
- `01-store/internal/rights/decide.go:10–36`: роли `domain`, `domainagent`, `<sub>domain` и never для `domain/`.
Эти пути судом и повтором не проверены: директива не исполнялась.

## Что видела модель
Нормы в M. Модель прочитала `01.2-store.norms.md` (вызов 16) и `acceptance/2/README.md` (34). Догадки нет.

## Мнение
Исход — **движок**, по трём дефектам:
1. директива словаря не реализована;
2. её `not_executed` не останавливает зависимые шаги;
3. при нехватке сокета роли запрос молча уходит от другой роли.

Вторая причина — **норма**: R033 не называет исход шагов после директивы, которую судья не исполнил. Нужна фраза: «steps after a directive that the judge did not execute are `not_executed` with its reason». Кандидат судом не проверен: ни один из 16 случаев ему не засчитывается.

Предложение (ворота линии судьи): заглушка с `-rights {rights}` в шаблоне. `@rights store none` перезапускает её без флага, и `GET /v1/rights` должен дать 404. Заглушка без сокета `domain.sock` даёт шагу `@as domain` исход `stand`, а не ответ чужой роли.

## Вопросы ревьюеру
1. Стоит ли включить `@rights store` в список R033 (без файла шаги сценария теряют смысл), или достаточно общей фразы о шагах после `not_executed`-директивы?

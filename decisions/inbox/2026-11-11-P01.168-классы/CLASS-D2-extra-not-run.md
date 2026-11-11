# D2 — цель P/01.1/extra: движок не исполняет пробы, итог `not_executed stand`

**Случаев:** вся цель — 60 строк `forms/extra.scenarios.tsv` (`not_executed`, причина `stand`) и 16 записей `forms/extra.tsv` (`not_executed`, причина `fault`). Ни одного GREEN и red.

## Наблюдение движка
`out-diag/claude/P_01_1_extra/engine.json`: `result: not_executed`, `reason: stand`, `classes: {}`, `steps: []`. У строк `response: ""`, то есть запроса не было. У записей — `extra-absolute-target`, `extra-cl-and-te`, `extra-early-refusal`, … с причиной `fault`. `engine.log` пуст.

Повтор `replay188` (`/home/pilot/owner-receipts/P01.188-court-claude-20261111/replay188/`, INDEX.md §«P/01.1/extra»): тот же движок `ef7dcf9b` со вставкой трассировки шагов сценария (`engine-src.diff`, `scenario_verdict.go`), тот же J-вход, тот же `cand-diag/claude`.
- `out/P_01_1_extra.json` равен диагностике: `not_executed stand`; 60 строк `not_executed stand` с пустым `response`; 16 записей `not_executed fault`. `progress`: `P/01.1/extra rc=0`.
- **Трассы `trace/P_01_1_extra.jsonl` нет**, а у пяти других целей она есть. Цикл шагов сценария (`executeScenarioSteps`) для extra не вызывался ни разу, и ни одной строки `extra.scenarios.tsv` движок кандидату не отправил.
- stderr демона кандидата за прогон цели (`stderr/P_01_1_extra.txt`, то же в `out/P_01_1_extra.log`): `configstore: started box srv-a, store …/data/configstore`, затем `configstore: stopping`. Демон `store1` поднялся, отказов и ошибок нет. Остановил его движок в конце цели.

Стенд кандидата поднялся, это подтверждено повтором. При неподнятом стенде было бы `blocked readiness:role`, как у всех веток красного набора на `fc47755d`: стенд там не стартует, K1 P01.127 (`summary-official.txt`, строки 14–74). Трассировка повтора не покрывает пробу готовности `executeExtraDoor`, поэтому сам `GET /v1/status` повтором не виден. Его видно по коду и по отсутствию `blocked`.

Код движка `ef7dcf9`:
- `internal/engine/run.go:140–178`. До исполнения каждая строка инвентаря получает `not_executed` с причиной `stand` (`:165`), каждая запись — `fault` (`:176`, слово причины проб `P/01/production`).
- `internal/engine/run.go:314` → `run_stand.go:366–387` `executeExtraDoor`. Для семейства `extra` движок ждёт ролевой сокет и шлёт один `GET /v1/status`, больше ничего. Комментарий: «Extra probes are described in the acceptance README, not in the scenario table, so there is deliberately no selected scenario row to replay here.»
- `verdict.go:203–222` — первый `not_executed` строки становится итогом цели.

Строки `extra.scenarios.tsv` движок не исполняет ни на каком кандидате. Код это показывает, повтор подтверждает: трассы шагов нет, стенд кандидата поднят и не падал. Кандидат на исход не влияет.

## Норма (J-вход `49e62279`)
- `common/acceptance/forms/targets.routing.tsv:2`, слово `extra`: «the rows of forms/extra.tsv for the target: a probe runs as the scenario of its id in the files of tables, a probe without one is not_executed (no_machine_form), a precondition runs first (scenarios none)».
- Там же `:13`: `P/01.1/extra	extra	["Platform/01-store/acceptance/1"]	none	["Platform/common/acceptance/forms/extra.scenarios.tsv"]	[]	whole`.
- `forms/extra.scenarios.tsv:1–3` — машинная форма проб (P01.142): «one scenario per probe of forms/extra.tsv, named by its id … every scenario runs on its own instance».
- `forms/extra.tsv:4` — `precondition` идёт первым; если она красная, остальные — `precondition:<id>`. Для P/01.1/extra это `extra-parameters` (`:9`).
- `spec/acceptance.norms.md:61` (P/AC-R030) — закрытый список причин `not_executed`. Слов `stand` и `fault` для этой цели в нём нет. `no_machine_form` — только для пробы без сценария, а здесь сценарий есть у каждой из 16 проб.

## Код кандидата
Профиль `01-store/acceptance.yaml`: `stand.store1` (тот же запуск `configstore`, что `store`) и `keys.role_header: X-Configstore-Role` — всё, что требует строка `runner-targets.tsv:3`. Интерфейсы есть, `blocked` не было.

## Что видела модель
В M нет ни `extra.scenarios.tsv`, ни `extra.tsv`, ни `targets.routing.tsv`: они только для судьи. Пробы описаны прозой в `01-store/acceptance/1/README.md` (§«The instance of the chapter»). Модель прочла его целиком (вызов 24). К исходу класса это отношения не имеет.

## Мнение
Исход — **движок**. Семейство `extra` по `targets.routing.tsv` исполняет пробы как сценарии, а движок делает только пробу готовности. Причины `stand` и `fault` вне закрытого списка R030.

Главная причина — модель линии судьи. Вторая — **цикл** линии судьи: ворота движка (P02.40, 345/345) не требовали, чтобы строки `tables` цели `extra` исполнялись. Комментарий в `run_stand.go:367` написан до машинной формы P01.142.

Правило для ворот: на заглушке с поднятым стендом каждая строка `extra.scenarios.tsv` получает GREEN или red. `not_executed` допустим только с причиной из R030 (`precondition:<id>`, `no_machine_form`, `MissingBinding`).

Цель о кандидате ничего не говорит. Пробы extra (тело на пределе, ключ из KEY_BYTES, CL+TE, ранний отказ, абсолютная цель запроса и др.) у кандидата Claude не проверены.

## Вопросы ревьюеру
1. Записи `forms/extra.tsv` (16) и строки `extra.scenarios.tsv` (60) — две единицы одного случая или разные? Сейчас движок считает обе. По R031 GREEN снимают обе, но в счёте пакета это 16 или 76 случаев?
2. Нужно ли в R030 отдельное слово для цели, которую движок не исполнил по своей вине (дефект судьи), или это всегда red класса `runner`?

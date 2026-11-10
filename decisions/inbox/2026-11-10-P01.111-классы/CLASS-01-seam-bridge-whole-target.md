# C01. Без приёмника моста движок блокирует цель целиком

**Суть.** В `--bindings` нет `SEAM_BRIDGE.json`. Из-за этого движок блокирует всю цель (`blocked`, причина `binding:SEAM_BRIDGE`), и ни один шаг обычных сценариев (`scenarios.tsv`) не исполняется. Раннер исполняет эти шаги, и они зелёные.

**Случаев:** 808. Это door у `c36e6ac` (345) и у `d9d15b0` (345), daemon у `c36e6ac` (118). Ключ в `summary.json`: `runner_GREEN_engine_not|not_executed|stand|GREEN`.

## Норма
- `Platform/common/acceptance/README.md:348` (раздел «Seam adapter protocol»): «A seam records an actual call and its effects; it does not replace an ordinary process scenario, a native vector, a stand neighbour or a reading obligation that it did not execute.»
- `README.md:376` («Explicit test-side seam bridge»): «The current Runner without this receiver has `MissingBinding`/`NOTEXEC`; publishing the format does not implement or activate it.»
- `spec/acceptance.norms.md`, P/AC-R050: «A descriptor serves the target whose id is its `scope`, or, when the scope is that id followed by `#` and the name of a scenario or case, that one case». Мост — вход строк швов, а не всей цели.
- `forms/targets.routing.tsv`: `P/01.1/door` — engine `run`, «run — the scenarios.tsv of the first directory». Каталог `Platform/01-store/acceptance/1` содержит отдельно `scenarios.tsv` и `seams.tsv`.
- P/AC-R007: `blocked` — «a required interface or part of the composition is absent before execution; this is not a test result». P/AC-R030: причина `not_executed` — имя отсутствующего интерфейса или ключа.

## Случаи-образцы (`c36e6ac`, `P/01.1/door`; J `01-store/acceptance/1/scenarios.tsv`)
| Случай | Раннер (`out/c36e6ac/P_01_1_door/runner/P-01.1-door.json`) | Движок (`out/c36e6ac/P_01_1_door/engine.json`) |
|---|---|---|
| 28-admission, шаг 13, строка 171: `POST /v1/write {…"cas":"","not_after":4102444800,"id":"2802"}` → `200 {"index":"$c"}` | ok, шаг 13 | `not_executed`, reason `stand`; итог цели `blocked binding:SEAM_BRIDGE` |
| 35-batch-guards, строка 256 | ok, шаг 8 | `not_executed stand` |
| 23-extra-cmd, строка 113 | ok, шаг 2 | `not_executed stand` |

У `P/01.3/daemon` (`out/c36e6ac/P_01_3_daemon`) то же: 08-floor-replay:28, 20-spoil-row:190, 12-copy-refused:56 — у раннера ok, у движка `not_executed stand`. Отчёт раннера door: `runner/P-01.1-door.txt`, «acceptance GREEN» и raw-пробы ok.

## Код движка
- `internal/engine/run_bindings.go:49-66` (`executeSeamBridge`). Если строки `seams.tsv` выбраны, а `SEAM_BRIDGE.json` нет: `c.addBlocked("binding:SEAM_BRIDGE")`. Пометка ставится на цель, а не на строки швов.
- `internal/engine/verdict.go:191-194` (`deriveRunReport`): `if len(ctx.blocked) != 0 { report.Result = ResultBlocked; report.Reason = ctx.blocked[0] }`. Любая блокировка делает итогом всю цель.
- `internal/engine/run.go:103-107`: все шаги описи заранее помечены `not_executed("stand")`. Шаги `scenarios.tsv` так и остались непройденными.

## Мнение представителя
**Движок.** Нормы разделяют швы (`seams.tsv`, вход — мост) и обычные сценарии (`scenarios.tsv`). Без моста не исполняются только строки швов, с причиной `MissingBinding`/имя интерфейса. Блокировка всей цели — дефект движка. Механическое правило: шаг таблицы не из `seams.tsv` не может быть `not_executed` с причиной моста, и итог цели не может быть `blocked binding:SEAM_BRIDGE`, если обычных шагов больше нуля.

## Вопросы ревьюеру
1. Какая точная закрытая причина у строки шва без моста: `MissingBinding`, `NOTEXEC` или имя интерфейса `SEAM_BRIDGE` по R030? Каким тогда будет итог цели, если все обычные шаги GREEN, а строки швов не исполнены: `not_executed` (по R031 GREEN снимает любая неисполненная строка) или иное?
2. Нужна ли в норме явная фраза «без моста не исполняются только строки `seams.tsv`»? Или достаточно README:348 и R050?

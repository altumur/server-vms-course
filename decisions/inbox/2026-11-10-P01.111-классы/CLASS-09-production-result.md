# C09. production: итог цели `blocked` против `not_executed`; раннер цель не исполняет

**Суть.** На `P/01/production` (оба кандидата) у движка итог цели `blocked`, причина `binding:D7`. При этом все 30 записей описи — `not_executed`, причина `fault`. Раннер цель не исполняет вовсе: префлайт сообщает, что C-исполнение этой цели не поддерживается.

**Случаев:** две цели по 30 записей. Расхождением в счёте не считались: у раннера нет отчёта.

## Норма
- `spec/acceptance.norms.md`, P/AC-R047 (N6.5): «a required D7 binding is absent — `not_executed`, the reason is `clock`, `storage`, `progress` or `fault`».
- P/AC-R049: «On the stub of R027 the target lists its whole inventory and calls the interfaces of each entry; every entry whose binding the stub does not qualify is `not_executed`. A stub establishes no production result».
- P/AC-R030: причины `not_executed` для `P/01/production` — из таблицы N6.5.
- P/AC-R007: `blocked` — «a required interface or part of the composition is absent before execution; this is not a test result».
- `common/acceptance/README.md:452`: «… retain `MissingBinding`…» для отсутствующего поставщика D7.

## Наблюдения
- Движок, `out/c36e6ac/P_01_production/engine.json`: `result blocked`, `reason binding:D7`, 30 записей, например `{"name":"RUN-W01","result":"not_executed","reason":"fault"}`.
- Раннер, `out/c36e6ac/P_01_production/runner.log`: «format2 preflight: P/01/production: C execution supports P/01, connected P/02, P/03/process, P/04/process, P/05/process, P/06, P/08-10 chapters and explicit SDK/package target ids». Отчёта нет.

## Мнение представителя
**Норма или движок.** Записи движка по R047 верны. Спорен итог цели: R007 называет `blocked` отсутствием интерфейса или состава до исполнения, а R047 для отсутствующей привязки D7 даёт записи `not_executed`. Если привязка D7 — «часть состава», движок прав. Если это вход записи, итог цели — `not_executed` (по R031 GREEN снимает любая неисполненная запись). У раннера — предел инструмента, цель не исполняется.

## Вопросы ревьюеру
1. Какой итог цели требует норма, когда все записи `not_executed` из-за отсутствующей D7 и нет входа N6.2: `blocked` или `not_executed` (с какой причиной)? Если норма не решает, это пробел.
2. `MissingBinding` (README:452) — это слово отчёта или только имя состояния в прозе? В закрытых причинах R030/R047 его нет.

# D2 — `ASSERT $a != $b $c`: движок `not_executed assertion`

**Случаев:** 10 «раннер GREEN, движок нет» — door 5, inproc 5 (сценарии `05-unconditional:17`, `07-no-reuse:29`, `31-delete-cas-id-order:201`, `33-batch-all-or-nothing:235`, `34-batch-create-edit-delete:244`). Ворота добавляются в P01.125.

## Суть
Шаг-директива `ASSERT $a != $b $c` (попарная различность связанных значений, HTTP не шлётся) у движка не исполняется: `not_executed`, причина `assertion`. Раннер — `ok: true`.

## Норма
`Platform/common/acceptance/README.md`, строка 255: «`ASSERT $a != $b [$c …]` | the named values are pairwise distinct; no HTTP is sent». Строка 256: «`ASSERT <term> <op> <term>` | a comparison of bound values …». Строка 309: «`$name` | binds a JSON string or number (a number — for `ASSERT`; P/01.1 binds only strings …); the first occurrence binds, the following ones compare».

## Образцы
| Шаг (`Platform/01-store/acceptance/1/scenarios.tsv`) | Движок (`out/P_01_1_door/engine.json`) | Раннер (`acc/P_01_1_door/P-01.1-door.json`) |
|---|---|---|
| `05-unconditional` 5, строка 17: `ASSERT $a != $b $c` | `not_executed`, reason `assertion` | step 5, line 17, `ok: true` |
| `07-no-reuse` 5, строка 29: `ASSERT $a != $b $c` | `not_executed`, reason `assertion` | step 5, line 29, `ok: true` |
| то же в inproc | `out/P_01_1_inproc/engine.json` — те же 5 строк | `acc/P_01_1_inproc/P-01.1-inproc.json` — `ok: true` |

## Код движка
`internal/engine/scenario_verdict.go:571–590`:
```go
func evaluateScenarioAssertion(expect string, bindings map[string]any) (bool, string) {
	fields := strings.Fields(strings.TrimPrefix(expect, "ASSERT "))
	if len(fields) < 3 {
		return false, "assertion"
	}
	if strings.HasPrefix(fields[0], "$") && fields[1] == "!=" {
		seen := make([]any, 0, len(fields)-2)
		for _, term := range fields[2:] {
			value, ok := assertionTerm(term, bindings)
			if !ok {
				return false, "assertion"
			}
			…
```
Ветвь попарной различности сравнивает только `fields[2:]` (`$b $c`), без `fields[0]` (`$a`); при отсутствии связи (`assertionTerm` — `scenario_verdict.go:628`) — `false, "assertion"`, что вызывающий код отмечает как `not_executed` с закрытой причиной. Точная причина отказа на этих пяти шагах (нет связи или иное) по отчёту не видна — отчёт не несёт диагностики.

## Мнение представителя
Исход — **движок**: норма 255 однозначна. Главная причина — модель; вторая — **цикл**: ворота P01.107 `directives` требуют «ASSERT исполняется, если сценарий не прерван», но принимают `not_executed` с закрытой причиной как исполнение-или-отметку. Правило для P01.125 (предлагаемое): шаг `ASSERT` вне прерванного сценария не может быть `not_executed`; на заглушке значения связей предсказуемы (заглушка знает, что вернула), значит исход ASSERT проверяем механически — попарно различные связи → GREEN, совпадающие → red.

## Вопросы ревьюеру
1. Входит ли `$a` в множество попарно различных (по 255 — да: «the named values»)?
2. Если связь не установлена (предыдущий шаг не вернул поле), исход ASSERT — red, not_executed или прерывание сценария? Норма (строки 135, 309) это не называет явно.
3. Подходит ли правило для ворот или нужна иная формулировка?

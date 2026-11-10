# D5 — пробы extra: опись 15 строк, все `not_executed fault`; раннер — 3 своих группы проб GREEN

**Случаев:** раннер GREEN, движок нет — 3 (пробы раннера `full key (R29-01)`, `id fingerprint (run 36)`, `identity (R38-06)`); не GREEN у обоих — 15 (строки описи движка, у раннера таких случаев нет).

## Суть
Движок (после C11, P01.114) перечисляет все 15 строк `forms/extra.tsv` цели `P/01.1/extra` и каждой даёт `not_executed`, причина `fault`. Раннер исполняет три группы проб своим кодом и даёт GREEN. Строки `extra.tsv` — проза: колонки `probe` и `expect` описывают пробу словами («on a separate instance with rights on acc/: keys of acc/ at the boundary lengths in UTF-8 bytes …»), машинной формы запроса и ожидания нет.

## Норма
`Platform/common/acceptance/forms/extra.tsv` (заголовок `target id section probe expect norm`, 15 строк P/01.1/extra), разделы `Platform/01-store/acceptance/1/README.md` «the instance of the chapter», «extra fields of a command (K37-05)». `Platform/common/acceptance/README.md:190`: «does not carry the chapter-wide probes of the parameters and of raw HTTP: its result names the subset, and a target is green …». Закрытые причины `not_executed` — `Platform/common/acceptance/spec/acceptance.norms.md` (P/AC-R007, R024).

## Образцы
| Случай | Движок (`out/P_01_1_extra/engine.json`) | Раннер (`acc/P_01_1_extra/P-01.1-extra.json`, `report.json`) |
|---|---|---|
| `extra-full-key` | entry `not_executed`, reason `fault` | проба `full key (R29-01)` GREEN |
| `extra-forwarded-list` | entry `not_executed`, reason `fault` | — (у раннера нет такой пробы) |
| итог цели | `not_executed`, reason `fault` | `green: true` |

## Код движка
`internal/engine/run.go:141–145`:
```go
	for _, item := range inventory.entries {
		entry := item.report
		notExecutedVerdict("fault").applyEntry(&entry)
		ctx.entries = append(ctx.entries, entry)
	}
```
Все записи описи (и production, и extra) получают `fault` по умолчанию, затем `classifyProductionEntries` (`run_production.go:29–60`) переклассифицирует только записи production по нужде; для extra причина остаётся `fault`.

## Мнение представителя
Исход — **норма** (главное): пробы extra описаны прозой, исполнить их механически без знания урока нельзя (догадка №5 линии судьи; «опись extra» P01.86 дала строки, но не машинную форму пробы). Вторая — **движок**: причина `fault` — слово привязки D7 (сбои), для прозаической пробы оно неверно; нужна закрытая причина «нет машинной формы» (если такая есть в P/AC-R024) или новая. Схема: спека — главная.

## Вопросы ревьюеру
1. Есть ли в закрытом списке причин `not_executed` слово для «проба описана, но без машинной формы»? Если нет — это пробел нормы.
2. Требует ли норма (README:190, «the result names the subset») исполнения проб extra движком вообще, или достаточно перечня с исходом?
3. Раннер исполняет 3 группы проб своим кодом: это знание урока в судье — допустимо ли оно по P/AC-R002?

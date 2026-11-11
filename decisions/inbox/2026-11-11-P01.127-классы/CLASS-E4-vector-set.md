# E4 — сравнение `set` и замена `@bad` векторов revoked не исполняются: red на любом ответе

**Случаев:** 20 строк `P/01/vectors-revoked` с `class implementation, reason native` (`response: valid`). По повтору 16 из них кандидат отвечает верно (класс E4), 4 — неверно (класс K4: 3 строки здесь и 1 строка — отказ команды).

## Норма
J: `Platform/common/vectors/wire.tsv:75`, строка `common/revoked`: `expect` — `[{"variant":"","when":"true","code":0,"value":{"column":"expect","decode":"cell"}}]`, `compare` — `set`, `overrides` — `[{"variant":"","column":"expect","match":"@bad","compare":"value","value":{"literal":"@bad"}}]`; форма — `common/vectors/wire.md` (режимы сравнения).

## Код движка
`engine/internal/engine/run_vectors.go:367–391` (`vectorNativeMatches`): режим берётся только из `item.wire.Compare`, столбец замен `match`/`@bad` не читается. `compareVectorValue` (`:505–521`):
```go
switch mode {
case "", "value": …
case "subset": …
case "raw": …
default:
	// The first-wave vector declarations use value/subset. Other closed
	// modes remain a mismatch until their package-specific observer exists.
	return false
}
```
Режим `set` попадает в `default` → несовпадение всегда.

## Повтор (кандидат, `/srv/calib-p0180/p0126/tmp/vec127/revall.txt`)
| Строки | Ответ кандидата | Ожидание | Совпадение по множеству / `@bad` |
|---|---|---|---|
| ok, no-final-lf, empty, leading-zeros, upper, same-value, zero, decimal-looking, skip, both-union, crl-only | `["3c","1a2b"]`, `["ab"]`, `[]`, … | то же как множество | да (11) |
| bad-0x, bad-colon, bad-nonhex, bad-sign, both-revoked-bad, both-crl-bad | `"@bad"` | `@bad` | да (6) |
| bad-space, bad-leading-space-comment, bad-crlf | `["ab"]`, `["ab"]`, `["ab","cd"]` | `@bad` | нет → K4 |
| absent (`@absent`) | код 2, без ответа | `@bad` | нет → K4 (у движка `stand command`, см. E5) |

Совпадает 17 строк: 16 из 20 красных «native» и строка, которая у движка не красная (её нет — все 21 красные). Значит, 16 красных «native» — вина движка.

## Мнение представителя
Исход — **движок**: форма `wire.tsv` закрыта, режим `set` и замена по `match` в ней объявлены. Главная причина — модель (линия судьи); вторая — **цикл**: ворота P01.81/P01.107 проверяли векторы на пакетах с `value`/`subset` и не подавали `set`.

Правило для ворот: на заглушке для каждого режима `compare`, который встречается в `wire.tsv`, и для каждой замены `match` верный ответ — GREEN, перестановка элементов при `set` — GREEN, лишний элемент — red.

## Вопросы ревьюеру
1. Какие ещё пакеты первой волны объявляют `compare` вне `value`/`subset`/`raw` (поиск по `wire.tsv`)? Все они сейчас красные на любом ответе.

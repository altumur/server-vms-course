# C03. Директивы `@big(N)` и `ASSERT` не исполняются (inproc)

**Суть.** На `P/01.1/inproc` у `c36e6ac` 15 шагов красные у движка (`red implementation expectation`). В их запросах `@big(N)` не раскрыт. Ещё 5 шагов `ASSERT` у движка `not_executed` с причиной `assertion`. У раннера все эти шаги зелёные.

**Случаев:** 20 (15 + 5). Ключи: `runner_GREEN_engine_not|red|implementation|GREEN` и `…|not_executed|assertion|GREEN`.

## Норма
- `Platform/common/acceptance/README.md:250`: «`@big(N)` — a substitution in any part of the request: a string of N bytes `x`; inside a JSON string — before serialization; the substitutions of a request go in the order `@spoil($name)`, then `$name`, then `@big(N)`».
- `README.md:255-256`: `ASSERT $a != $b [$c …]` — «the named values are pairwise distinct; no HTTP is sent». `ASSERT <term> <op> <term>` — сравнение связанных значений.
- `README.md:309`: `$name` связывает значение. «the bindings of an attempt are fixed only after the whole step matches; they live until the end of the scenario».

## Случаи-образцы (`c36e6ac`, `P/01.1/inproc`; J `01-store/acceptance/1/scenarios.tsv`)
| Случай | Раннер (`out/c36e6ac/P_01_1_inproc/runner/P-01.1-inproc.json`) | Движок (`…/engine.json`) |
|---|---|---|
| 19-key-too-long, шаг 3, строка 90: `POST /v1/write {…"guard":{"key":"acc/19-key-too-long/@big(1100)",…}}` → `400 {"kind":"badkey"}` | ok | `red implementation expectation` |
| 22-body-edge, шаг 2, строка 111: `GET …/c1` → `200 {"items":null,"index":""}`. Шаг 1 (строка 110): `@big(4194304)` в теле → `413` | ok | `red implementation expectation` |
| 33-batch-all-or-nothing, шаг 11, строка 235: `ASSERT $i != $j $k` | ok | `not_executed assertion` |
| 31-delete-cas-id-order, шаг 4, строка 201: `ASSERT $d1 != $p1` | ok | `not_executed assertion` |

## Код движка
- В коде движка нет подстановки `@big`: поиск `@big` и `big(` по `internal/` ничего не находит. Запрос уходит с буквальным `@big(1100)`.
- `internal/engine/scenario_verdict.go:92-101`: для `ASSERT` вызывается `evaluateScenarioAssertion(item.expect, bindings)`. Если причина непуста, шаг становится `notExecutedVerdict(reason)`. Видимо, привязки `$i`, `$j`, `$k` из прежних шагов не сохранились.
- `scenario_verdict.go:205-227` (`directiveReason`): закрытые причины только у `@spoil`, `@rights`, `@import`.

## Мнение представителя
**Движок.** `@big(N)` и `ASSERT` входят в словарь директив общей приёмки, раннер их исполняет. Механическое правило: шаг с `@big(N)` отправляется с раскрытой строкой (заглушка видит N байт `x`); шаг `ASSERT` даёт GREEN или red, но не `not_executed`, если связанные имена определены прежними шагами.

## Вопросы ревьюеру
1. Есть ли в норме закрытый список директив, которые судья обязан исполнить, а не пометить `not_executed`? Если нет, это пробел (сейчас R030 даёт закрытые причины только для пяти особых случаев).
2. Пять `ASSERT`: не исполнены из-за потери привязок (ошибка движка) или потому, что движок не дошёл до шагов, где имена связываются (следствие `@big`)?

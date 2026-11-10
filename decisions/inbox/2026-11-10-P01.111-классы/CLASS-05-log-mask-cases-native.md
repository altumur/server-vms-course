# C05. log-mask `cases.tsv`: движок красит все строки по `native`

**Суть.** На `P/01/vectors-log-mask` у `c36e6ac` движок красит все 39 строк `cases.tsv` (`red implementation`, reason `native`, `response valid`). Раннер те же 30 строк засчитывает GREEN, 9 красных у него общие. На мутанте `red/mut-log-mask` у движка та же краснота, что на базе: движок мутант не различает.

**Случаев:** 30 (`runner_GREEN_engine_not|red|implementation|GREEN`), плюс неразличимый мутант.

## Норма
- `Platform/common/vectors/wire.tsv:63` (`common/log-mask`, `cases.tsv`): заголовок `-,raw,masked,note` (без заголовка в таблице), вход `raw`, `expect` `[{"variant":"","when":"true","code":0,"value":{"column":"masked","decode":"text"}}]`, `compare` `raw`, `native` `{"type":"string","frame":"json"}`.
- `common/vectors/log-mask/README.md`, раздел `cases.tsv`: `masked` — что показывает журнал; ячейка читается байт в байт.
- `common/vectors/wire.md` — грамматика `expect`/`compare`/`native`.

## Случай-образец (`c36e6ac`)
- J `common/vectors/log-mask/cases.tsv:25`: `raw` = `at rtsp://cam:554, again`, `masked` = `at rtsp://cam:554, again` (адрес без учётных данных не маскируется).
- Ответ кандидата у раннера, `out/c36e6ac/P_01_vectors-log-mask/runner/P-01-vectors-log-mask-processes/case-0012/stdout.bin`: `{"exit_code":0,"stdout_b64":"ImF0IHJ0c3A6Ly9jYW06NTU0LCBhZ2FpbiIK",…}`. Внутри — JSON-строка `"at rtsp://cam:554, again"` и LF.
- Раннер, `…/runner/P-01-vectors-log-mask.json`: `case line-25`, `ok true`, `executed true`.
- Движок, `…/engine.json`: `{"table":"…/cases.tsv","line":25,"result":"red","class":"implementation","reason":"native","response":"valid"}`. То же у строк 16, 20, 27, 42.

## Код движка
- `internal/engine/run_vectors.go:76-80`: `if !c.vectorNativeMatches(item, response) { redVerdict(ClassImplementation, "native") }`.
- `run_vectors.go:367-391` (`vectorNativeMatches`): код выхода, затем `vectorExpectedValue(item, expectation["value"])` (с `decode: text`), `vectorActualValue(item, response.stdout)`, `compareVectorValue(mode, …)`. Режим `compare` равен `raw`. Видимо, ожидаемое (`decode: text` — текст ячейки) и фактическое (JSON-строка из native-кадра) сравниваются в разных видах.

## Мнение представителя
**Движок.** Ответ кандидата в форме native: JSON-строка, значение равно ячейке `masked`. Раннер засчитывает его, движок красит все строки одинаково, в том числе на мутанте. Механическое правило: на заглушке с заведомо верным ответом (значение = ячейке `expect`, кадр native) строка вектора — GREEN, с заведомо неверным — red. Тот же контроль «правильное и неправильное значение в верной форме», что в P01.81, но с `decode: text` и `compare: raw`.

## Вопросы ревьюеру
1. `compare: raw` с `decode: text` по `wire.md`: что именно сравнивается — байты ячейки `masked` с байтами строки после снятия JSON-кадра? Однозначна ли грамматика?
2. Девять строк, красных у обоих: кандидат или общая ошибка чтения таблицы?

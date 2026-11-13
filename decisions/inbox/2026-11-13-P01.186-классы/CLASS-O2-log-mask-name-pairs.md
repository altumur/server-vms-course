# O2 — имя пары, которое раскодируется в «&pwd»: читать ли его вместе со своим значением

**Цель:** P/01/vectors-log-mask, Opus 8. **Случаев:** 1 строка (cases.tsv:43). **Класс:** спецификация; вторая причина — кандидат.

## Случай
J `Platform/common/vectors/log-mask/cases.tsv:43`:
`?%26p%2577d=hunter2` → ожидание `?***`; пояснение строки: «a name that decodes to «&pwd» is read as pairs: the name goes with the value (A7; S17)».
Имя `%26p%2577d` до неподвижной точки: `%26`→`&`, `%2577`→`%77`→`w`, итог `&pwd`.

## Наблюдение движка
`out/opus8/P_01_vectors-log-mask/engine.json`, `rows[]`: строка 43 — `red implementation`, `response: valid`, `detail: native bytes differ`; остальные 38 строк GREEN. У Opus 7 на том же J и движке красны строки 20, 37 и 43 (`P01.290-circle-newJ-b-20261112T2156Z/out/claude7-pin/P_01_vectors-log-mask/engine.json`). Строки 20 и 37 Opus 8 прошёл, 43 — нет у обоих.

## Место в коде кандидата (чтение, не запуск)
Строка без `://`, путь — свободные пары: `01-store/internal/logmask/mask.go:1045–1104` (`freePairs` → `classify(name, val, 0, true)`, `:1091`). `classify` (`mask.go:971–994`):
- `isSecret("%26p%2577d")`: `normName` раскодирует имя в `&pwd` (`mask.go:385–398`); `&` не разделитель слова (`isNameSep`, `mask.go:372`), слово одно — `&pwd`; оно не равно `pwd` и не начинается с него → не секрет.
- Имя с `%`: `decodeFix` → `&pwd`, есть `&` → `partsSecret("&pwd")` (`mask.go:996–1003`): части `""` и `pwd`, ни в одной нет `=` → не секрет.
- Значение без `%` → `maskNone`.

Значит, вывод — `?%26p%2577d=hunter2` без маски; ожидание — `?***`. Окно кандидат не запускало: вывод по коду.

Opus 7 читает так же: `attempt7-review-inputs/candidate-claude/01-store/internal/logmask/address.go:224–231` (`hiddenName`: раскодированное имя содержит `=&;` и в нём есть секретная пара).

## Норма
- `Platform/common/contracts/url-credentials.md:161–168`, A7. (б): значение раскодировать, разрезать по `&` и `;`, «a part with `=` is read as a pair by A5». Последний абзац: «The name of a pair with `%` which, decoded, contains `=`, `&` or `;` (`?pass%3D…=1`), is read the same way. The name is masked together with the value.»
- `Platform/common/contracts/log-mask.md:39–41`: «A7 (a pair hidden by escaping — the whole value; a name decoded into pairs goes away with the value)».

Пример нормы (`?pass%3D…=1`) — имя с `=` внутри. Для имени, где после раскодирования есть только `&`, текст не говорит, что последнюю часть имени надо склеить с собственным `=значением` пары. Буквальное «read the same way» (часть с `=` — пара) даёт ответ кандидата. Ожидание вектора требует склейки: `&pwd` + `=hunter2` → часть `pwd=hunter2` → секрет → имя и значение под маску.

## Что видела модель
`cases.tsv` — только в J; в M каталог `common/vectors/log-mask/` содержит один `README.md` (окно сверило `M-tree-final` и `ls-tree` J). Строку 43 модель не видела. Нормы A7 и `log-mask.md` в M есть. Генерация без ворот (`P01.289-…/CONTROL-TASK-attempt7.md:2`). В `GUESSES.md` кандидата догадки о маске нет. Две независимые генерации (Opus 7, Opus 8) прочли абзац одинаково.

## Исход
- **Спецификация:** абзац A7 об имени допускает два чтения. Вектор закрепил одно из них, которого текст не называет. По правилу P01.164 R7 это ближе к «спецификации»: развилку модель не отметила догадкой, но буквальный текст даёт её ответ, и два кандидата сошлись.
- **Кандидат (вторая):** перечень `=`, `&`, `;` в условии намекает, что `&` без `=` тоже должен что-то давать; внимательное чтение могло вывести склейку.

## Что предлагается
- **Норма:** в A7 (`url-credentials.md:167`) добавить: «Decoded, the name is joined with `=` and the value of its pair, and the result is cut and read as in (b): `?%26p%2577d=hunter2` → `?***`.» Тогда строка 43 следует из текста.
- **Кандидат:** правки нет (генерация с нуля).

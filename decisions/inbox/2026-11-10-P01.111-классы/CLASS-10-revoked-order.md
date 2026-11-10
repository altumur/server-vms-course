# C10. revoked: мутант «обратный порядок» — README сравнивает множества, `wire` говорит `value`

**Суть.** Мутант `red/mut-revoked` (коммит `e4e8958`, `vectors/revoked/revoked.go:127`: обратный порядок серийных номеров в ответе). Раннер засчитывает GREEN 21/21, движок красит 4 строки (3, 6, 7, 20). В RESULT-P01.80 это записано как «раннер пропустил мутант». По README revoked порядок не судится, поэтому вопрос в том, ошибка ли это вообще.

**Случаев:** 1 мутант, 4 строки. На базе `c36e6ac` оба судьи дают GREEN 21.

## Норма
- `Platform/common/vectors/revoked/README.md:24-25`: «compares: the set of the revoked serials (by integer value) equals `expect`, or the file is rejected as wrong at `@bad`». Сравнивается множество.
- `revoked/README.md:19`: `expect` — «a JSON array of the serials of the file by value — the canonical notation: … in ascending order of value, without repeats». Это каноническая запись ожидаемого в таблице, а не требование к порядку ответа.
- `common/vectors/wire.tsv:75` (`common/revoked`, `cases.tsv`): `expect` `value` из столбца `expect` (`decode: cell`), `compare` `value`, `native` `{"type":["array","string"],"frame":"json"}`. Если `compare: value` по `wire.md` — точное равенство значений JSON, то массив в другом порядке не равен.

## Наблюдения
- Раннер, `out/red-mut-revoked/P_01_vectors-revoked/runner/*.txt`: «01-store vector-revoked 21/21; GREEN».
- Движок, `…/engine.json`: `result red`, красные строки 3, 6, 7, 20.

## Код
- Раннер, `runner/c_revocation_vectors.py:94-104`. Комментарий «README: the set of revoked serials by integer value per center … Order is not judged.», затем `matches = serial_set(got) == serial_set(expected)`.
- Движок сравнивает по `compare: value` из `wire.tsv` (`run_vectors.go:384-391`, `compareVectorValue`).

## Мнение представителя
**Норма.** README revoked (сравнение множеств) и форма `wire.tsv` (`compare: value`) противоречат друг другу. Раннер следует README, движок — форме. Мутант нарушает только каноническую запись, а не смысл. Пока противоречие не снято, мутант не годится для красного набора. Правка спецификации: либо `wire.tsv:75` получает режим сравнения множеств (если он есть в `wire.md`), либо README требует порядок.

## Вопросы ревьюеру
1. Есть ли в `wire.md` режим `compare` для неупорядоченного массива? Если есть, `wire.tsv:75` ошибочна. Если нет — пробел грамматики.
2. Согласен ли ты, что мутант `mut-revoked` исключается из красного набора до правки нормы?

adr: 0093 (34)

# Ревью текста: ADR-0093 доп. (34) (Claude)

Доп. (34) на origin/main f63280995. Сверено с `harness/rules/words.json` курса:
- `kinds["segment.lost"]` = `segment|recording.*lost|lost.*recording|куск|запис`;
- `actions["cam disarm"]` = `disarm` (+ `disarm_ru` при `guard`);
- `not_armed` = `disarm|not armed|без охраны`;
- `conditions.armed` = `armed|on guard|охран`.

Проверено в Python 3.12 `re`.

**Счёт: Б 0, С 0, М 2.** Только М: по слову «Архитектора» — в нормы без дополнения.

**М1. Из трёх слов `segment.lost` нового — одно.**

| Текст | нынешнее выражение |
|---|---|
| the camera lost recording | да (`lost.*recording`) |
| камера теряет запись | да (`запис`) |
| the camera loses recording | **нет** |

Добавить нужно только `loses`, например `los(?:es|t)\s+(?:\S+\s+)?recording`. Вектор на «loses». «Lost recording» и «теряет запись» норма уже пускает, и в перечне правок после замера (V/11.13 `:33`) их стоит назвать как уже бывшие, а не новые. Иначе вектор «новое слово» пройдёт и без правки, и ничего не проверит.

**М2. «Off guard» — у действия и у `value: false`.** «Снятие с охраны» в (31) вошло в оба места: `cam disarm` и `not_armed` условия `armed` (V/11.13, строка `value: false`). (34) говорит «снятие с охраны» без места. Добавить `off guard` с границами с обеих сторон и в `actions["cam disarm"]`, и в `not_armed`. Тогда «if the camera is off guard» — `value: false`, а не ошибка. `conditions.armed` его не ловит: там `on guard`, и «off guard» с `armed: true` получит ошибку, как и нужно.

## Сверено и держит

- Предел «caught off guard» назван, его ловят показ и наблюдение. «Off guard» вне охраны редко стоит рядом с камерой, так что цена мала.
- `cam arm` и `conditions.armed` «off guard» не задевают: у `arm` две границы, `on guard` — другое слово.

adr: 0093 (34) нормы

# Ревью норм: vms/words-93e, ADR-0093 доп. (34) (Claude)

Слияние 171fa1521 на main: `harness/rules/words.json` (`segment.lost`, `cam disarm`, `not_armed`, `conditions.armed`), V/11.13 Н1.6 (перечень правок, «Чтение слов», строка действия, пределы), `rules-words` 139 случаев (+5), `adr-norms.tsv` +2. Выражения прогнаны в Go 1.22.10 `regexp` на восьми фразах. Все пять векторов на месте: `segment-loses`, `disarm-off-guard`, `armed-off-guard`, `armed-off-guard-true`, `disarm-caught-off-guard-gap`.

**Счёт: Б 0, С 0, М 1.** Внесено по (34) и моему ревью. «Lost recording» и «теряет запись» названы как уже бывшие в словаре, новое — только `loses`.

Решение «Спецификации VMS» «и в `conditions.armed`» верно, и оно поправляет моё М2 (34). Я писал, что `conditions.armed` «off guard» не ловит, и это хорошо. Но строка «условие `armed` — `hit` `conditions[kind]`» судит вид условия раньше значения. Без «off guard» в `conditions.armed` верный план `armed: false` на «if the camera is off guard» отказался бы словами `the request does not ask for armed`. Теперь вид ловится, значение судит `not_armed`, обратное — вектор `armed-off-guard-true`.

| Текст | Совпало |
|---|---|
| the camera loses recording | `segment.lost` |
| if cameras lose recording | **ничего** |
| when the camera is losing recording | **ничего** |
| take Lobby Cam off guard | `cam disarm`, `not_armed`, `conditions.armed` |
| if the camera is off guard | то же |
| we were caught off guard | то же — предел (34) |
| takeoff guardrail | ничего |

**М1. «Lose» и «losing» вне `los(?:es|t)`.** «If cameras lose recording» во множественном числе и «is losing recording» — обычные формы, а выражение их не берёт. Предложение: `los(?:e|es|t|ing)` и вектор на «lose». В остальном граница держит: «takeoff guardrail» не «off guard».

## Сверено и держит

- `off guard` — с границами с обеих сторон в трёх местах. `cam arm` его не задевает. `conditions.armed` его ловит намеренно, а значение судит `not_armed`.
- Предел «caught off guard» назван в V/11.13, вектор `known_gap`.
- `adr-norms.tsv`: п. 1 — НОРМА с решением «решила», предел — ПРЕДЕЛ.

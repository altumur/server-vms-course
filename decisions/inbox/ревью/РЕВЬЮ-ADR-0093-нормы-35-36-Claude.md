adr: 0093 (35)–(36) нормы

# Ревью норм: vms/words-93g, ADR-0093 доп. (35)–(36) (Claude)

Слияние fb90db1f8 на main: V/11.13 Н1.6 (`kind_hit` `:140`, слова состояния `:148`, строка действия `:171`, строки `kind` `:161`, `:162`, `:193`), `harness/rules/words.json` (`silent`, `lost_bare`, `lost_contact`, `arm_put`), `rules-words` 151 случай (+10), `adr-norms.tsv` +5. Новые выражения прогнаны в Go 1.22.10 `regexp` на восьми фразах.

**Счёт: Б 0, С 0, М 1.**

| Текст | Совпало |
|---|---|
| if cameras drop off / when the feed dropped off | `silent` |
| the camera lost recording | `lost_bare`, `segment.lost` → `kind_hit` у `silent` нет: верно |
| it is lost | `lost_bare` → `silent` и `disappeared` |
| we lost contact | `lost_contact`, `silent` → у `disappeared` нет |
| put    on guard (имя вырезано `cut`) | `arm_put` |
| put the lobby entrance cam on guard (без `cut`) | нет: четыре слова между, работу делает `cut` |

**М1. «Lost» без продолжения» — не то, что делает выражение.** V/11.13 `:140`: «`lost_bare` („lost“ без продолжения)». `lost_bare` = `(?:^|…)lost(?:$|…)` находит «lost» где угодно, и в «lost recording» тоже. Отсечение делает не выражение, а условие «нет `hit` `segment.lost` и нет `hit` `lost_contact`». Скобку «без продолжения» заменить на «„lost“ словом». Иначе реализация станет требовать конец фразы после «lost».

## Сверено и держит

- `kind_hit` — одно определение для трёх мест: `kind` триггера, событие `wait_event`, `kind` шага `det`. Голое «lost» отсекается проверкой, как `default_no`, по всему тексту, предел назван. Вектор `lost-two-events` его держит.
- `drop(?:s|ped|ping)? off` с границами в `silent`.
- `arm_put` — по `cut(t)`: имена камер не съедают предел «до трёх слов между». Голого «on guard» у `cam arm` нет: оно у `conditions.armed`, вектор `arm-bare-on-guard`.
- Векторы на каждую ветку:
  - `segment-lose`, `segment-losing`;
  - `silent-drops-off`;
  - `lost-bare-silent`, `lost-bare-disappeared`;
  - `lost-recording-not-silent`;
  - `lost-contact-not-disappeared`;
  - `lost-two-events`;
  - `arm-put-on-guard`, `arm-put-on-guard-names`;
  - `role-other-language`.
- `adr-norms.tsv`:
  - (35) п. 1 — НЕ НОРМА, эталон Пилота;
  - п. 4 — ПРЕДЕЛ;
  - (36) — НОРМА с пределом «по всему тексту».

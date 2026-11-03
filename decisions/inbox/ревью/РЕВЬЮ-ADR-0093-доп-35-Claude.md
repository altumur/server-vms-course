adr: 0093 (35)

# Ревью текста: ADR-0093 доп. (35) (Claude)

Доп. (35) на origin/main. Сверено с V/11.13 Н1.6 и `harness/rules/words.json` курса; столкновения проверены в Python 3.12 `re` с границей доп. (25).

**Счёт: Б 0, С 1, М 1.** Пп. 1, 3, 4 чисты. П. 4 согласен с (19) п. 5, (21) п. 1: имена ролей — `has`, слова событий — `said` дословно. Предел «русская просьба к английскому миру спрашивает раз на правило» назван.

## С

**С1. «Lost без „recording“ и „contact“» — условие, которого выражение одним `hit` не скажет.** П. 2. Голое `lost` с границами совпадает и там, где речь о записи:

| Текст | `lost` | `segment.lost` | `silent` сейчас |
|---|---|---|---|
| the camera lost recording | да | да | нет |
| if recording is lost | да | да | нет |
| it is lost | да | нет | нет |
| we lost contact with lobby cam | да | нет | да |

Реализация, которая добавит `lost` в `kinds.silent` и `kinds.disappeared` выражением, пропустит план `silent` на «the camera lost recording». Это подмена `segment.lost` → `silent`, слой её не поймает. Другая реализация сделает исключение. Исходы разойдутся.

**Предложение.** Записать форму, как у `default_no`: `lost` засчитывается `silent` и `disappeared`, только когда нет `hit` `kinds["segment.lost"]` и нет `lost contact`. Ключ `lost_other` и проверка «и нет …» — по образцу `default_yes` / `default_no`. Векторы: `lost-recording-not-silent`, `its-lost-both`.

## М

**М1. Формы «drop off».** П. 2 называет «drops off», «dropping off». «Drop off» («if cameras drop off») и «dropped off» — те же события в других формах. Взять `drop(?:s|ped|ping)?\s+off` с границами, как формы `run` (доп. (31) п. 2).

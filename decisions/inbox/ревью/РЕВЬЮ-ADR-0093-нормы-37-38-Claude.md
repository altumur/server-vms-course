adr: 0093 (37)–(38) нормы

# Ревью норм: vms/words-93i (2c2d3f351), ADR-0093 доп. (37)–(38) (Claude)

Сверено: V/11.13 Н1.6 (строки `:172` названный шаг, `:173` та же камера), Н1.7 (`:207`), пределы (`:202`), `harness/rules/words.json` (`asks_step`, `same_camera`, `kick off`, `stop(s|ped) recording`), векторы +12. Выражения прогнаны в Python 3.12 `re`.

**Счёт: Б 0, С 1, М 0.** (37)–(38) внесены по словам: `asks_step` узкий, мои М1, М2 (38) учтены; «та же камера» при одной камере-триггере по id верна; широкий триггер включает `cam` без `unit`; Н1.7 сужает предел «выпавший шаг не виден».

| Текст | `segment.lost` | `lost_bare` | прочее |
|---|---|---|---|
| **If the bag is lost, start recording on Lobby Cam** | **да** | да | — |
| when an item is lost near the door, keep recording | **да** | да | — |
| If Lobby Cam stops recording, raise an alarm | да | нет | — |
| When the lpr camera reads a plate, ask the guard | нет | нет | `asks_step.ask` |
| turn on the siren on that same camera | нет | нет | `same_camera` |
| scan the archive of Lobby Cam | нет | нет | `asks_step.det scan` |

## С

**С1. Исключение «lost» судит по всему `kinds["segment.lost"]`, а там `lost.*recording` — обычная просьба о пропаже уходит в вопрос.** V/11.13 `:140` `kind_hit`: «`lost_bare`, когда нет `hit` `kinds["segment.lost"]`». В `kinds["segment.lost"]` стоят `recording.*lost|lost.*recording` без предела между и `запис`. «If the bag is lost, start recording on Lobby Cam» — самая частая форма просьбы «пропал предмет — пиши». Она даёт `hit` `segment.lost` («lost … recording»), голое «lost» отсекается, и верный план `disappeared` получает `the request does not speak of disappeared`. Предел «по всему тексту» (`:202`) говорит о просьбе «с потерей записи», а здесь потери записи нет. Тот же текст после (37) п. 3 «stop(s) recording» не задет, но `.*` — задет.

**Предложение.** Исключение — отдельным узким ключом `segment_lost_phrase`: `los(?:e|es|t|ing)\s+(?:\S+\s+)?recording`, `recording\s+(?:is\s+|was\s+|got\s+)?lost`, `stop(?:s|ped)?\s+recording`. Без `.*` и без `запис`: «lost» английское, а `запис` в русской просьбе стоит почти всегда. `kinds["segment.lost"]` для своей прямой сверки остаётся широким. Векторы: `lost-bag-start-recording` (верный `disappeared` проходит), `lost-recording-not-disappeared` (прежний).

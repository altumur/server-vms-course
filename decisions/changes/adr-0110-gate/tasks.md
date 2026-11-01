# Задачи adr-0110-gate

ADR-0110 доп. (5), разбор, шаг 3 «Суд по цели»: Д-1, Д-2, Д-8. Векторы `may-107`…`may-115`. Реализацией не прогнаны. Сценарии стенда — шаг 11 разбора.

| Код | Что менять | Спец. | Go | Python |
|---|---|---|---|---|
| C10-TARGET-JUDGE-01 | `may`: `unit: "any"`, вход `anywhere`, шаги 3, 6, 6а | [x] | [ ] | [ ] |
| C10-TARGET-JUDGE-01 | двери вида: `wide`, вход, фильтр записей и строк таблиц, `withheld`, `X-Withheld` | [x] | [ ] | [ ] |
| C10-TARGET-JUDGE-01 | правки единиц домена: `write` по кластеру цели | [x] | [ ] | [ ] |
| C10-TARGET-JUDGE-01 | сводка `anywhere`: проход держателя, `sealed`, копия `domain/grants`, `door.pass` второго вида | [x] | [ ] | [ ] |
| C10-TARGET-JUDGE-01 | `Unit.labels`, `Unit.about` | [x] | [ ] | [ ] |
| C06-AT-READ-01 | чтение у другого члена `GET /domain/at/<кластер>/<sub>/<имя>[/<id>]`, `calls`: `GET domain/at/<s>/<имя>` (ADR-0111 п. 15) | [x] | [ ] | [ ] |
| C08-VIEW-PULSE-01 | `domain.view_pulse`, `members[].servers[].pulse` (ADR-0111 п. 2) | [x] | [ ] | [ ] |

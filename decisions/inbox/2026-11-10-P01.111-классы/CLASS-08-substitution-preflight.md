# C08. `{rights}` в команде векторов: движок не отклоняет профиль при префлайте

**Суть.** Профиль `c36e6ac`, а значит и всех веток красного набора от него, содержит команду векторов `vectors.01-store/rights-evaluator` с подстановкой `{rights}`. На зачётном пути с этим профилем раннер отклоняет профиль целиком до исполнения. Движок профиль принимает и судит цели.

**Случаев:** уровень профиля: все цели зачётного прогона. Записано на `P/01.1/door` у `c36e6ac` и `red-empty`. Сам счёт калибровки шёл на диагностическом профиле без этой строки.

## Норма
- `Platform/common/acceptance/PROFILE.md:13`: «Duplicate keys, unknown fields and incorrect field types are format errors before builds or processes start».
- `PROFILE.md:78-82`, «Substitutions»: «A template may use only the names available to that particular command. … An unknown name, field lookup, conversion or format specifier is a format error. … The names available to a command are the column `names` of its row in `forms/profile-substitutions.tsv`».
- `forms/profile-substitutions.tsv:86`: `vectors	*	[…все модули…]	["input"]	["input"]`. Командам векторов доступна только `{input}`.

## Наблюдения
- Раннер, `/srv/calib-p0180/formal/c36e6ac/P_01_1_door/runner.log`: «format2 preflight: …/01-store/acceptance.yaml:vectors/01-store/rights-evaluator: unavailable substitution rights». Цель не исполнена, профиль отклонён.
- Движок, `/srv/calib-p0180/formal/c36e6ac/P_01_1_door/engine.json`: `result blocked`, `reason binding:SEAM_BRIDGE`, 345 шагов. Движок пошёл судить, префлайт формата не отклонил.
- То же на `formal/red-empty/P_01_1_door`.

## Код движка
- Проверки имён подстановок по `profile-substitutions.tsv` до исполнения в `internal/profile` не видно: поиск `substitution` и `unavailable` ничего не находит. Точное место пусть подтвердит ревьюер.

## Мнение представителя
**Движок.** Норма однозначна: неизвестное для команды имя — ошибка формата до сборки и процессов. Механическое правило: профиль с подстановкой, которой нет в `names` строки `profile-substitutions.tsv`, отклоняется до исполнения. Заглушке дать такой профиль, и движок должен отказать.

## Вопросы ревьюеру
1. Отказ формата профиля — это итог каждой цели (какой: `blocked`?) или отказ всего прогона? Что говорит норма?

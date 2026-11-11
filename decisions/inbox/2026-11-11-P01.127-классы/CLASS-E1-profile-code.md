# E1 — профиль с необязательным полем `code` отвергнут движком целиком

**Случаев:** 84 запуска зачётного прогона (7 сборок × 12 целей) без отчёта: `judge: run: assembly: assembly module 01-store: …/acceptance.yaml: unknown field "code"` (`/srv/calib-p0180/p0126/out/fc47755d/P_01_1_door/engine.log` и все остальные).

## Норма
J-вход `f11bf34d`, `Platform/common/acceptance/PROFILE.md`:
- строка 47 (таблица полей): «`code` | no | Mapping of the names of the code checks of the lesson of the module to Go symbols of the implementation; `{}` is allowed»;
- строка 153: «The field `code` serves the generation cycle (ADR-0133 addendum (39)). The acceptance checks only its shape, a mapping of keys to nonempty single-line strings, and does not use it otherwise».

## Код движка
`engine/internal/profile/profile.go:101–103`:
```go
allowed := map[string]bool{"format": true, "implementation": true, "module": true, "spec_version": true, "build": true, "unit": true, "stand": true, "keys": true, "adapters": true, "vectors": true, "artifacts": true}
if err := exactFieldSet(fields, allowed, "format", "implementation", "module", "spec_version", "build", "stand", "keys", "artifacts"); err != nil {
```
`code` в `allowed` нет; `exactFieldSet` (`profile.go:173–178`) — «unknown field».

## Кандидат
`01-store/acceptance.yaml` кандидата `fc47755d` — блок `code:` (17 строк) по форме: ключи — имена `forms/code-rules.tsv`, значения — непустые строки. Диагностика: тот же профиль без блока принят.

## Мнение представителя
Исход — **движок**: норма однозначна. Главная причина — модель (линия судьи); вторая — **цикл**: ворота линии судьи подавали профиль заглушки без поля `code`, и отказ не был виден. Правило уже назначено (P02.25): ворота подают профиль с каждым необязательным полем PROFILE.md (`unit`, `adapters`, `vectors`, `code`), в том числе с `{}`, и ждут приёма.

## Вопросы ревьюеру
1. Достаточно ли строк 47 и 153, чтобы требовать от движка проверку формы `code` (отказ на нестроковом значении), а не только приём поля?

---
kind: запрос
date: 2026-10-23
author: «Спецификация VMS» (перевод главы V/03.3)
blocks: нет
export: cammeta-specs f6f3895 (курс 175b75527)
status: открыт
---

# Запрос: правка навыка — снять строку реестра `V/03 no-openapi`

С главой V/03.3 у урока есть контракт двери шлюза — `VMS/03-live/spec/03-live.api.openapi.yaml` (маршрут `whep`). Строка
`skills/lesson-spec/exceptions.tsv` `V/03	no-openapi	…` (`87edf38c6`, запрос «реестр V03») больше не нужна.

**Рекомендация.** Удалить строку `V/03 no-openapi`; `check_spec.py VMS/03-live/03-live.md` — PASS без исключений урока.

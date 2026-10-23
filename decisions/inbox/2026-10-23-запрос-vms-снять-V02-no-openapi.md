---
kind: запрос
date: 2026-10-23
author: «Спецификация VMS» (перевод главы V/02.5)
blocks: 02-rec — нет (проверка урока красная только этой строкой)
export: cammeta-specs 6e51975 (курс 0b26e3b70)
status: решён
---

# Запрос: правка навыка — снять строку реестра `V/02 no-openapi`

`check_spec.py VMS/02-rec/02-rec.md` — `stale exception no-openapi: the contract exists`: глава V/02.5 переведена, контракт
`VMS/02-rec/spec/02-rec.api.openapi.yaml` есть. **Рекомендация:** снять строку `V/02	no-openapi` в
`skills/lesson-spec/exceptions.tsv` (как условлено при её добавлении, `9ae999a43`).

## Решение
Решён (2026-10-23, «Архитектор»): строка `V/02 no-openapi` снята из `skills/lesson-spec/exceptions.tsv`; `check_spec` при устаревшей строке `no-openapi` всё равно проверяет контракт (`fdecc7988`).

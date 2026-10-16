---
kind: вопрос
adr: 0074, 0056, 0012
date: 2026-10-17
author: команда курса (OpenAI Codex)
---

# Confirmation: консоль стенда cam требует rec

## Контекст

Поправка 3 исполнена в `codex/course-adr74-confirm-tests-domain`, `6b90d03d`: загружается только `cam.subsystem.yaml`. Повтор domain — 139/51: `device_console` создаёт `SpecController`, который вызывает `catalog.near_known(cam)` и отказывает без rec из-за `near.of/prefer` (ADR-0056). Журнал: `/tmp/adr74-review-domain.log`. Domainvms — 206/0, boundary — 6/0. Платформу и спеки не меняли.

## Рекомендация

В `device_console` передавать контроллеру локальную тестовую копию cam через `dataclasses.replace(spec, near="none", near_of="", near_prefer={})`; каталог сохраняет исходную опубликованную cam. Консоль стенда редактирует строки, размещения не выполняет; достижимость доказана отдельно на testsub. Rec не загружать. Разрешить такую фикстуру; код до решения не пишем.

---
kind: запрос
date: 2026-10-23
author: «Спецификация VMS» (перевод главы V/01.1)
blocks: 01-cam — нет (механическая проверка урока откладывается; общий вызов зелёный)
export: cammeta-specs afb1c88 (курс 0d0b393de)
status: открыт
---

# Запрос: правка навыка — `check_spec` для уроков VMS в раскладке `VMS/NN-<имя>/`

**Какое правило мешает.** `skills/lesson-spec/scripts/check_spec.py:1811–1815` (`lesson()`): лекция принимается только как
`Platform/NN-<процесс>/NN-<процесс>.md` (тогда `platform_lesson`) или `<модуль>/NN-slug.md` прямо под корнем; иначе
`ERROR … expected module/NN-slug.md under repository root`. `references/validation.md:40–41` обещает: «Уроки VMS в
нормативной раскладке проверяются тем же вызовом с путём лекции, когда «Спецификация VMS» их переведёт». Раскладка VMS
— как у `Platform/` (ADR-0090 доп. (2)): `VMS/NN-<имя>/NN-<имя>.md`, нормы по главам `spec/NN.K-<имя>.norms.md`, id
`V/NN.K-MM`, приёмка `acceptance/K/`, id-map и каталог — `VMS/common/`.

**Что нужно VMS.** `check_spec.py VMS/01-cam/01-cam.md` → сейчас `ERROR VMS/01-cam/01-cam.md: expected module/NN-slug.md
under repository root` (ветка `vms/inventory`, глава V/01.1 переведена: `spec/01.1-cam.norms.md`, `spec/01.7-cam.norms.md`
— заглушка, `spec/01-cam.README.md`, `acceptance/1/`).

**Обход до решения.** Общий вызов `check_spec.py Platform/0*-*/0*.md` зелёный (таблицы VMS, манифесты `VMS/` через
загрузчик); проверка урока V/01 — чтением по чеклисту навыка, строкой долга в ХОД.

**Рекомендация.** В `lesson()` — ветка `lesson.parent.parent == root / "VMS"` → тот же разбор, что `platform_lesson`, с
параметрами модуля: префикс id `V/NN`, карта уроков `VMS/common/lessons.tsv` (колонка `subsystem` вместо `process`, без
`unit`), id-map и каталог `VMS/common/`, OpenAPI урока необязателен (у урока без своей двери — строка `no-openapi`
реестра, как у P/03, P/04); глава-заглушка (V/01.7: разделы Н0–Н5 без норм, пустой чеклист, ссылка на запрос) — допустима
без приёмки (строка реестра или признак в норме). `validation.md` — строка о раскладке VMS рядом со строкой о `Platform/`.

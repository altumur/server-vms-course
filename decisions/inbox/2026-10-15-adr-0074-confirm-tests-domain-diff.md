---
kind: отчёт
adr: 0074
date: 2026-10-15
author: команда курса (OpenAI Codex)
---

# ADR-0074: diff подтверждения границы тестов

Ветка `codex/course-adr74-confirm-tests-domain`, база `dcf2509c`, diff проверок — до `6c34f581`. Все проверки из `tests/domain` больше не импортируют VMS; `TESTS.tsv` покрывает 192 проверки и сохраняет 742 узла `assert`. Runtime платформы и продукт не менялись.

Результаты: domain 190/0, domainvms 206/0; unit 2050/1/2 — единственный отказ `platform_lists` (ожидаемое расхождение паритета), два пропуска console без jsdom. Журналы и SHA256: `windows/adr74-confirm/evidence.json`. Готово к чтению; слияние не выполнялось.

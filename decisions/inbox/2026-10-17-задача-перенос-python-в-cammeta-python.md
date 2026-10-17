---
kind: задача
adr: 0080, 0006, 0005
date: 2026-10-17
author: «Архитектор»
---

# Задача команды курса: реализация на Python — в репозиторий `cammeta-python`

## Контекст
Решение владельца 2026-10-17 (ADR-0080 доп. 15): курс остаётся спецификацией с приёмкой, реализация на Python
уходит в отдельный репозиторий `/Users/murat/w2c/cammeta-python`, как раньше порт на Go (ADR-0006).
**Не начинать** до слияния открытых веток команды (окно М10/1) и до сброса недельного лимита 2026-10-22.

## Что сделать
1. **Новый репозиторий с историей.** `git subtree split` или `git filter-repo` по путям реализации; в
   `cammeta-python` они лежат без префикса `Source/`. Переносится:
   - `Source/w2cplatform/**` кроме `console.js`, `console.css`, `console.html`;
   - `Source/vms/**` кроме `*.subsystem.yaml` и `*.shell.html` подсистем (спеки и страницы — данные курса);
   - `Source/deploy/`, `Source/gstvms/`, `Source/traces/`, `Source/README.md`;
   - `Source/tests/**` кроме `Source/tests/testdata/**`.
2. **В курсе по прежним путям остаются** `Source/vms/*.subsystem.yaml`, `Source/vms/*.shell.html`,
   `Source/tests/testdata/**`, `Source/w2cplatform/console.{js,css,html}`. Ни один из этих путей не меняется:
   продукт читает их `sync-course.sh` и тестами сверки.
3. **Чтение курса из `cammeta-python`** — переменной `W2C_COURSE_DIR` на закреплённый checkout курса, без
   угадывания пути (как `vmsworker/vms/coursedir_test.go` продукта). Тесты, читающие спеки, общие таблицы,
   приёмку и модуль консоли, берут их оттуда.
4. **Курс после переноса.** Удалить перенесённые файлы одним коммитом окна; ссылки на код в замороженных
   прежних уроках, `_notes-ru`, `CLAUDE.md`, `СЕССИИ.md` — перевести на `cammeta-python` или убрать (правило 6:
   без следов). ADR и отчёты ревью — история, не правятся. Тест на документы курса (каждый путь из `*.md`
   существует) — зелёный.
5. **Не трогать:** продукт, `sync-course.sh`, байты спек и общих таблиц.

## Проверка и отчёт
- в `Source/` курса нет `*.py`, `git ls-files Source` — только пути п. 2;
- `cammeta-python`: `tests/run.py`, `tests/cluster/run.py`, `tests/domain/run.py`, `tests/domainvms/run.py`
  с `W2C_COURSE_DIR` на курс после переноса — те же счёты, что на курсе до переноса;
- у продукта `W2C_COURSE_DIR=<курс после переноса> go test ./vmsworker/vms/ -run 'SpecParity|SpecLoad'` зелёный;
- отчёт — раздел «Исполнение» здесь же: хеши обоих репозиториев, счёты до и после, что передать «Ночному
  прогону» (фаза unit запускает тесты курса: путь и venv).

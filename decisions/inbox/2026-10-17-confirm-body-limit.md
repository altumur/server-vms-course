---
kind: вопрос
adr: 0074, 0080, 0082
date: 2026-10-17
author: команда курса (OpenAI Codex)
---

# Confirmation: два отказа М10/1 вне окна

## Контекст

Повтор unit: `test_storage_m10.py::test_native_shared_acceptance_uses_each_real_backend_without_a_door` и `test_the_unchanged_shared_acceptance_passes_through_a_separate_daemon_process` падают: шаг `22-body-edge` возвращает `body.limit=524288`, ожидается `1048576`. Н5 `М10_Platform/spec/01-storage.norms.md:235` и TSV требуют тело 1 МиБ, строку 512 КиБ. `configstore.py` задаёт MAX_BODY≈3 МиБ, но при HTTP-413 сообщает MAX_VALUE; NativeAPI повторяет это. Журнал `/tmp/adr74-confirm-unit-20261017.log`. Код и приёмку не меняли.

## Рекомендация

Исправить отдельным окном М10 настройку штатного обработчика на объявленный приёмкой предел тела и корректный `limit`, синхронизировать NativeAPI; TSV не менять. Платформенный runtime запрещён в Confirmation. Сначала исправление в main, затем повтор полного unit здесь; либо явно уточнить условие приёмки текущего diff до исправления М10.

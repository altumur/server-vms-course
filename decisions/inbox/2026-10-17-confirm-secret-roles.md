---
kind: вопрос
adr: 0074, 0019
date: 2026-10-17
author: команда курса (OpenAI Codex)
---

# Confirmation: main удалил платформенную роль из общей таблицы

## Контекст

Повтор unit после вливания main даёт дополнительный отказ `test_platform_lists.py::test_the_code_holds_the_tables_lists`: `spec.SECRET_ROLES` содержит domainpart, `platform_lists.tsv` — нет. Строку таблицы удалил `92a0f988` (fix(spec36), 2026-10-16). Это расходится с ADR-0074 C7 и решением `0fecb291`: domainpart остаётся платформенной ролью. Журнал `/tmp/adr74-confirm-unit-20261017.log`, отказ отдельно от разрешённого product-parity. Runtime и таблицу не правили.

## Рекомендация

Разрешить восстановить единственную строку `secret_roles<TAB>domainpart` в таблице курса той же веткой Confirmation; исполняемый код и проверку не менять. Затем повторить полный unit. Это восстанавливает согласованность таблицы с действующим ADR-0074.

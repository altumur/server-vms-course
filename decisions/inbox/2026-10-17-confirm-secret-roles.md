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

## Решение («Архитектор», 2026-10-17)

**Принято: строка `secret_roles<TAB>domainpart` возвращается** в `Source/tests/testdata/platform_lists.tsv` той же веткой
Confirmation; код и проверки не меняются. Основание — решение по `2026-10-15-c7-общее-имя-роли.md`: `domainpart` — слово
платформы (у продукта `RoleDomainPart`, `known.go`), «`secret_roles/domainpart` в `platform_lists.tsv` — байты продукта,
не трогать». Таблица продукта (`vmssubsystem/testdata/platform_lists.tsv`) строку держит, `spec.SECRET_ROLES` курса —
тоже. ADR-0074 п. 6 снял процесс `domainpart` и роль у спек, не имя платформы.

Находка K36-7-02 (прогон 36, Kimi) принята против этого решения: норма Н1.3 урока 7 сама ошибалась («domainpart снят
ADR-0074 п. 6»), а исправлена была таблица. K36-7-02 отклоняется; поправки «Спецификации» — задачей
`2026-10-17-задача-domainpart-в-нормах-урока-7.md`. ADR-0082, дополнение «Архитектора» 2026-10-17.

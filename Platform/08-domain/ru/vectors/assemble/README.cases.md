# Данные случаев только для судьи

Этот русский текст — производный от `vectors/assemble/README.cases.md`, руками не правится (ADR-0121).

Общие правила остаются в [README.md](README.md). Следующие исходные отрывки сохраняют прежние связи именованных случаев как материал только для судьи.

Ожидания зависят от байтов манифестов каталога (разбор ревью стадии A 8–10, № 37): `domain.books` (`from`, `key`, `pick`, `to`) и
`domain.names` манифеста `testsub2` из данных спецификации:

| Манифест | Файл | sha256 |
|---|---|---|
| `testsub` | [`Platform/common/data/testsub/testsub.subsystem.yaml`](../../../../common/data/testsub/testsub.subsystem.yaml) | `fc3bf70585646b078a8812edd0c92cd5c7d0c2e364b689273c5fd229aed7355b` |
| `testsub2` | [`Platform/common/data/testsub/testsub2.subsystem.yaml`](../../../../common/data/testsub/testsub2.subsystem.yaml) | `e4bfd9e0035dba5839018625bba20f7214176004fc2d0cb4f8d640015d915dbb` |

Байты `testsub2` сменились 2026-11-04 (дорожная карта 4.5): добавлен вид токена `vault` с `keep: true` в `domain.tokens`, затем переписаны комментарии шапки без имён файлов тестов; поля, от которых зависят ожидания этой таблицы, не тронуты — перепроверка оракулом не нужна.

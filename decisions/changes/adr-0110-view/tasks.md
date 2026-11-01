# Задачи adr-0110-view

ADR-0110 доп. (5), разбор `decisions/inbox/ревью/РАЗБОР-ADR-0110-2-Claude.md`, шаг 2 «Вид и снимок». Случаи `a110_*` корпуса, вектор вида `11-view-revision-status-servers`. Реализацией не прогнаны. Сценарии стенда — шаг 11 разбора.

| Код | Что менять | Спец. | Go | Python |
|---|---|---|---|---|
| C08-VIEW-TABLES-01 | `domain.view_tables`, `domain.view_status`; связи 137–139, связь 84; имена `tables`, `snapshot-tables` заняты | [x] | [ ] | [ ] |
| C08-VIEW-TABLES-01 | контроллер: `<sub>/snapshot-tables/<таблица>` при смене строк, потолок SNAPSHOT_TABLE_MAX, счёт `snapshot_tables_refused` | [x] | [ ] | [ ] |
| C08-VIEW-TABLES-01 | агент несёт семью, `ready` её не судит | [x] | [ ] | [ ] |
| C08-VIEW-TABLES-01 | проход держателя, шаг 3б: `domain/members/<член>/tables/<sub>/<таблица>` | [x] | [ ] | [ ] |
| C08-VIEW-TABLES-01 | `Unit.revision` обязателен, `Unit.status`, `members[].servers` | [x] | [ ] | [ ] |
| C08-VIEW-TABLES-01 | дверь `GET /domain/<sub>/tables/<таблица>?cluster=`, слово `not reported yet`; `calls`: `GET domain`, `GET domain/<s>/<rows>`, `GET domain/<s>/tables/<таблица>` | [x] | [ ] | [ ] |

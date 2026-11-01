# Задачи adr-0110-edit

ADR-0110 разбор, шаг 4; ADR-0111 п. 16. Случаи `a110_edit_*`. Реализацией не прогнаны. Сценарии стенда — шаг 11 разбора. Предел V/02.6 снимается: `rec/volumes` доходит до кластера из одного.

| Код | Что менять | Спец. | Go | Python |
|---|---|---|---|---|
| C08-KEPT-TABLES-01 | `domain.edit_tables`, двери таблиц домена, путь агента | [x] | [ ] | [ ] |
| C08-KEPT-TABLES-01 | `domain.edit_secrets`, конверт `m1` при приёме, открытие агентом | [x] | [ ] | [ ] |
| C08-KEPT-TABLES-01 | связка `POST /domain/edits`, применение пакетом | [x] | [ ] | [ ] |
| C08-KEPT-TABLES-01 | `by`, `iat`, `X-Agent-For`, суд человека у консоли члена | [x] | [ ] | [ ] |
| C08-KEPT-TABLES-01 | разбор ревью: `cas` вне отпечатка пакета, `revision` строки пакета, правила по keys, `new_id`, дверь `/domain/edits/stranded`, 403 stale без исхода, связи 152, 153, `cap` двери в `write`, `member_anywhere` | [x] | [ ] | [ ] |
| C08-REF-SIBLINGS-01 | `?id=`, `id` строки связки, 409 `siblings`; `conflict` теневого отчёта по одному id | [x] | [ ] | [ ] |
| C08-KEPT-TABLES-01 | к шагу 8: `calls` `domain/edits`, `domain/members`, `domain/placement`; адрес (cluster, id) без ref; `server` таблицы; `outcomes` незрителю по `by`; `made` исхода; `members[].url`, `PUBLIC_URL`; `ETag` снимка | [x] | [ ] | [ ] |
| C08-ROLE-SPREAD-01, C08-SHARED-FOLDERS-01 | к шагу 8: `calls` `domain/roles/lines`, `GET domain/memberof`; `lines` в `RoleView`; проход не трогает `unit:`; `GET /domain/memberof`; суд `/domain/batch` по строке | [x] | [ ] | [ ] |
| C08-NAME-UNIQUE-01 | имя кластера уникально на домен: приём (ADR-0110 доп. (8)) | [x] | [ ] | [ ] |
| C06-AT-READ-01 | журнал у другого члена `GET /domain/at/<кластер>/events`, `calls` `GET domain/at/events` | [x] | [ ] | [ ] |

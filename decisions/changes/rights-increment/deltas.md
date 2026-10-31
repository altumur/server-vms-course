# Дельты rights-increment

Сравнение: `git diff 2bbc46cda 293b0ae5b`. Строка называет место и смысл, норму читай в файле. Новые id нормы — в `Platform/common/id-map.tsv`, прежние id не сняты.

Подробные формы не повторяются. Двери — OpenAPI урока, слова отказа — `data/refusal-words.tsv` урока (P/06 +44 строки, P/08 +56), семьи — `data/<семья>.*` и `Platform/common/data/catalog.tsv`.

## P/01 Хранилище

`01-store/spec/01.1-store.norms.md`
- MODIFIED Н1 «Пакет»: `BATCH_GUARDS` действует кроме ролей `console` и `domain`, у `domain` остаётся вес тела.

`01-store/spec/01-store.api.openapi.yaml`
- MODIFIED схема `BatchCmd`: то же правило.

`01-store/spec/01.2-store.norms.md`, `01-store/acceptance/2/`, `01-store/spec/01-store.README.md`
- MODIFIED Н5 № 16, сц. 14, 16: 65 стражей у `domain` — 200, у иной роли — 400. Глава 11 сц. / 67 шагов, урок 75 / 704.

REMOVED: комментарий `BATCH_GUARDS ≥ ADMIN_ASSIGNED_MAX + 5`, потому что `ADMIN_ASSIGNED_MAX` стал своей константой.

## P/02 Установщик

`02-installer/spec/02.1-installer.norms.md`, `02.1-installer.schema.json`, `02.1-installer.relations.json`
- ADDED Н1 «Корень»: `door.pass.operations {step, limits?, service?}`, `display.tree.folders`.
- ADDED «Связи (Н1.4)»: 132–135. Маршрут `step` не под `routes`, `<s>/operations` только своя и при объявлении, маршруты браузера не `operations`.
- ADDED Н5 группы случаев `a95_*`, `a96_*`, `a98_sub_*`; чеклист P/02.1-39.
- MODIFIED Н1 «Корень», «Определения»: запрещённые имена `name`, `unit.rows`, `<tableName>`. `door.pass.calls[]` принимает `folders`, `<s>/operations`, двери домена.
- MODIFIED связь 131: `operations` среди своих имён.
- MODIFIED Н1.4, Н3 `загрузить_каталог`: `<s>/operations` только своя подсистема.
- MODIFIED чеклист P/02.1-20: 31 слово. Н5: 813 файлов, 157 `ok`, 656 `refused`.

`02-installer/spec/02.2-installer.norms.md`, `02.2-installer.view.schema.json`
- ADDED `door.pass.operations`, `display.tree.folders`.
- MODIFIED запрещённые имена, `door.pass.calls`.

`02-installer/spec/02.5-installer.norms.md`
- MODIFIED Н1.4 `console`: строки папок, членства и семьи операций.
- MODIFIED Н1.4а `domainagent`: точный ключ `domain/roles`.

Приёмка и данные `02-installer/`
- ADDED `acceptance/1/cases/`: 48 файлов, строки `verdicts.tsv`, `vectors/canonical/expect/corpus-a9*.json`.
- MODIFIED `acceptance/1/README.md`, `02-installer.README.md`, `acceptance/2/puts/testsub.subsystem.yaml`, `vectors/canonical/cases.tsv`, `expect/course-testsub.json`.
- MODIFIED `acceptance/5/variants/v12-check-rights/check/*.rights`: шесть выводов прав с новыми семьями.

## P/03 Воркер

`03-worker/spec/03.4-worker.norms.md`
- ADDED Н1.7: маршрут `step`, его зовёт только консоль.

## P/06 Консоль

ADDED главы, целиком
- `06-console/spec/06.8-console.norms.md`: папки кластера, Н0–Н5, P/06.8-01…18.
- `06-console/spec/06.9-console.norms.md`: групповые операции, Н0–Н5, P/06.9-01…18.

ADDED к главам: `acceptance/8/` (12 сц. / 189 шагов), `acceptance/9/` (2 сц. / 8 шагов), `vectors/op-step/`, `data/folders`, `memberof`, `operations`, `opsteps`, `opdone`, `opcount`, `opbusy`, `operations-turn`, `operations-epoch`.

`06-console/spec/06.1-console.norms.md`
- ADDED Н2 «Версии»: строка индекса у папки и членства.
- ADDED Н2 «Лента изменений», сброс 5: сменился состав папки или папка удалена при области `folder:`.
- ADDED Н3 `удалить`: снятие единицы из папок тем же пакетом.
- ADDED Н3 `пакет`, шаг 6а: строки папок и членства.
- MODIFIED Н2 «Лента изменений»: форма `key`, `revision: 0`, охват, сброс 3 с ролями, фильтр через `may`, операции `service` по `by` записи.
- MODIFIED Н2 «Пакетная дверь»: допустимые семьи.
- MODIFIED Н3 `лента`: префиксы папок и операций, память `members`, надгробие папки, пометка смены состава.
- MODIFIED «Решает реализация» п. 10: номер ленты называет и назначения ролей.

`06-console/spec/06.2-console.norms.md`
- ADDED Н3 «перезапечатать при старте»: обход строк шагов.

`06-console/spec/06.3-console.norms.md`
- ADDED Н1.9: записи `folders`, `<s>/operations`, двери домена; раздел «Двери домена».
- MODIFIED Н1.9 «Строки пакета», «Не входят»: строки папок и итог шага; `/operations` снята из запретов, причина дополнена тревогой.

`06-console/spec/06.4-console.norms.md`
- ADDED Н2 «Подсистема и группы»: `sub` события, группа роли решает по `of`, быстрый путь.
- ADDED Н3 `жнец`: ссылки на жнецов папок и операций.

`06-console/spec/06.5-console.norms.md`
- ADDED Н1.2: ключ `tree.folders`.
- MODIFIED Н2 «Полные формы»: `/folders` без префикса подсистемы.

`06-console/spec/06.7-console.norms.md`
- MODIFIED Н1: чтение `domain/roles`.
- MODIFIED Н1.8, Н2, чеклист P/06.7-17: `POST /domain/move` — администратор домена, а не строка `admin` кластера.
- MODIFIED Н1.9: входы `roles`, `sub`, поля `/session`.

`06-console/spec/06-console.api.openapi.yaml`
- ADDED `/folders`, `/folders/{id}`, `/{sub}/operations` и четыре двери операции. `/session` несёт `sub`, `role`, `admin`.

Прочее: `06-console.README.md` (142 нормы, 140 сц. / 1495 шагов, 37 пунктов «Решает реализация»), лекция `06-console.md`, `README.md`, `lifecycle.md`.

REMOVED: строка «`POST /domain/move` → грант `admin` этого кластера», замена выше.

## P/07 Модуль консоли

`07-console-module/spec/07-console-module.norms.md`
- ADDED Н1.5 `tree`: дерево по папкам.
- ADDED Н5 `module-folders`, чеклист P/07-06.
- MODIFIED Н1.4 `reads`, `writes`, `order`: `/folders` только при `display.tree.folders`.
- MODIFIED Н1.5 `objects`: `folder:<id>`.
- MODIFIED Н1.5 `may`: сигнатура `may(cap, ref, sub?)`, ранг `none`, ярусы, неизвестный вход, `admin: true`.

`КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md`
- ADDED §5 п. 7 «Папки», отмечен долгом продукта.
- MODIFIED §5 «Права»: поля `/session`, область `folder:`.

`07-console-module/spec/07-console-module.README.md`: P/07-01…06.

## P/08 Домен

`08-domain/spec/08.4-domain.norms.md`
- ADDED Н1.3а «Группы и роли», Н1.3б «Таблица ролей члена», Н1.3в «Встроенная роль `admin` и управляющий».
- ADDED семьи `domain/groups/<имя>`, `domain/roles/<имя>`.
- ADDED Н1.3: `rewrite`, стражи доказательства, `GUARD_RETRIES`.
- ADDED Н1.9 `grant_admin`.
- ADDED Н2: двери групп, ролей, `POST /domain/batch`.
- ADDED Н3 «группы и роли»; в «двери людей» шаги 5б, 8а, сверка новых видов, срок, сверка роли `admin`; в «гранты» шаги 3б, 3в, 5а.
- ADDED Н4: `no such group`, `no such role`, `unknown member`, `bad batch`, `admin only`, `builtin`, `too many admins` и другие слова Н1.3а–Н1.3в.
- ADDED Н5 сц. 24–37, чеклист P/08.4-10…16.
- MODIFIED Н1: владеет группами и ролями, пишет `audit.alarms/<роль>`.
- MODIFIED Н1.1: поля `title`, `email`, `expires`, `pw_by`; `domain/disabled` ведёт и срок; метка `role:<имя>`.
- MODIFIED Н1.2 `check`: имя в `domain/disabled`.
- MODIFIED Н1.3: `line` с `sub`, `role:`, `none`, `folder:`; `domain/grants/domain` и строка управляющего; `last_admin` — только доказанные бессрочные; `carry` с `roles` и `held`; `unreadable` в две ступени.
- MODIFIED Н1.5: выход `unavailable`, группа управляющего.
- MODIFIED Н1.9 `first`: первый администратор — назначением роли, одним пакетом.
- MODIFIED Н2: двери людей и грантов, статус цели; журнал, тревога `domain.rights_via_backend`.
- MODIFIED Н3 «дверь людей» шаги 7а, 8, 9; «гранты» шаги 3а, 4; «Гонки».

REMOVED из Н1.9 `first`: прямая строка `{admin, *}` и порядок «грант, затем человек». Прямая строка у прежних установок остаётся действующей (Н1.3в `direct_line`).

`08-domain/spec/08-domain.api.openapi.yaml`
- ADDED `/domain/batch`, `/domain/groups`, `/domain/groups/{name}`, `/domain/roles`, `/domain/roles/{name}`.
- MODIFIED двери людей и грантов.

`08-domain/spec/08.0-domain.norms.md`
- MODIFIED Н1.9: таблица дверей, «Версии», «Память повторов» — группы, роли, пакет; у пакета условие — `cas`.
- MODIFIED Н5, чеклист P/08.0-03, 04: сц. 37.

`08-domain/spec/08.5-domain.norms.md`
- MODIFIED Н1.3, Н1.7: `sub` — подсистема книги, только прямые строки, `grant too wide` по рангу.
- ADDED Н5 № 14. Глава 7 сц. / 70 шагов.

`08-domain/spec/08.8-domain.norms.md`
- MODIFIED Н1.5 `state`: группы и роли.
- MODIFIED Н1.7: заморозка групп, ролей, пакета; проход доводит новые виды.
- ADDED Н1.8 `no_admin`.
- ADDED Н5 № 18, чеклист P/08.8-10. Глава 13 сц. / 122 шага.

Приёмка 8.4: шаги сц. 02/19, 21 и 17/3, 5 переписаны под назначение роли. Глава 33 сц. / 498 шагов, урок 106 сц. / 1326 шагов.

Прочее: `08-domain.README.md`, лекция `08-domain.md`, `data/groups.*`, `data/roles.*`, `data/users.layers.tsv`, `data/grants.outcomes.tsv`.

## P/09 Агент

`09-agent/spec/09.1-agent.norms.md`
- ADDED Н1.4 `member_roles`, семья `domain/roles`, Н5 № 27, чеклист P/09.1-35.
- MODIFIED Н1: владеет `domain/roles`.
- MODIFIED Н1.4: поле из `held` не удаляется, копия стареет по шагу 4.
- MODIFIED Н1.10: журналы ролей `audit.alarms/<роль>`.
- MODIFIED семья `domain/grants`: строка с `sub`, `role:`, `none`.

Приёмка: глава 22 сц. / 249 шагов, урок 27 / 311. `09-agent.README.md`: P/09.1-01…35, 43 нормы. Данные: `data/roles.*`.

## P/10 Консоль домена

`10-domain-console/spec/10-domain-console.norms.md`
- ADDED Н1.3а «Путь `backend` к дверям домена».
- MODIFIED Н1: чтение `domain/roles/<имя>`, `domain/groups/<имя>`.
- MODIFIED Н1.3а `pass`: группы, роли, пакет.
- MODIFIED Н1.5: вход `roles`, `iat`, строка управляющего.
- MODIFIED Н4 `unavailable`.

`10-domain-console/spec/10-domain-console.api.openapi.yaml`
- ADDED передачи групп, ролей, пакета.

Приёмка: сц. 15 шаг 8, `root` назначением, `admin: true` в `/session`.

## Общее

`common/contracts/may.md`
- ADDED вход `sub`, `roles`, `unread`, `iat`, `unit.chains`; выход `unavailable`.
- ADDED шаги 4а, 7а, 7б, 7в; разделы «Уровень группы роли», «Нечитаемая группа».
- MODIFIED шаги 5, 6, 7: отбор по `sub`, группы ролей, `folder:`. Ранг `none`.
- MODIFIED «Векторы»: 106 строк, `covers.tsv` 19.

`common/contracts/gate-and-pass.md`
- ADDED раздел «Подсистема проверки», стражи членства, цена.
- ADDED `roles_in`, `need` папок и операций.
- MODIFIED `caps`, `scope` с `folder:`, `session`, `domain`, «Отказы сторожевой», запись билета с `iat`.
- REMOVED `need`: `POST /domain/move → admin на *`, замена — шаг 1 или шаг 4а.

`common/contracts/forwarding.md`
- ADDED заголовок `X-W2C-Via-Worker`, заявленный признак; двери домена групп, ролей, пакета.

`common/contracts/domain-envelopes.md`
- ADDED поля `held`, `roles` в `sealed`; читатель пропускает поля вне перечня.

`common/contracts/turn.md`
- ADDED столбец «Очередь операций».

`common/contracts/store-client.md`
- MODIFIED предел стражей: у роли `domain` числом нет.

Данные и прочее
- MODIFIED `common/data/README.md`: заполнители `<i>`, `<корень>`.
- MODIFIED `common/data/catalog.tsv`: семьи папок, операций, групп, ролей; писатель `domain` у `audit.alarms/<роль>`.
- MODIFIED схемы семей `*/data/*.schema.json`, 115 файлов: копия определений с новой строкой гранта, смысла сверх Н1.3 нет.
- MODIFIED `common/vectors/`: `may`, `family-read/05`, `06`, `08`, `09`, `README.md`.
- ADDED `common/id-map.tsv`: 47 строк новых id.
- MODIFIED `module-design.md`: порядок глав 6.8, 6.9, пакет `op-step`.
- MODIFIED `Source/tests/testdata/testsub.subsystem.yaml`: ключ дерева, долг продукта в `ХОД-Спецификация.md`.
- ADDED `skills/lesson-spec/exceptions.tsv`: две строки `8/own`, `9/own`.

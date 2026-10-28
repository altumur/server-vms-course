# Курс ServerVMS: что читать любой сессии

Этот файл подхватывается автоматически. Он только указывает, где что лежит; содержание в самих файлах.

## Правила для всех сессий
- `СЕССИИ.md` §1 — правила для всех сессий: принципы владельца, вопрос с решением, отчёт «Сборке» о правках продукта, git по файлам (без `-A`, `--amend`, `stash`; worktree на ветку; пушит main курса «Лекции»), одно имя на обеих сторонах, переименование без следов, словарь границы, решение владельца это файл в `decisions/`.
- `СЕССИИ.md` §2–§3 — состав сессий, кто чем владеет, первый промпт каждой.
- Строка остановки (ADR-0083 доп. (57)): ход, после которого сессия остаётся без работы, кончается строкой `СТОП: <почему> | ЖДУ: <чего> от <кого/события>` — последней в окне и перезаписью в `/private/tmp/cammeta-status/<сессия>.txt` (время UTC первым полем); снова в работе — там же `РАБОТАЮ: <что>`.

- `ИНФРАСТРУКТУРА.md` — машины (CT 102, CT 103), доступы, очередь удалённых проверок, выгрузка; `tools/sessions/` — запуск сессий, реестр адресов `/Users/murat/w2c/cammeta-status/sessions.tsv`, статус.

## Решения и принципы
- `decisions/README.md` — индекс ADR. Прежде чем спорить с решением, найди его номер; новое решение владельца записывает та сессия, которая его услышала (`.cursor/rules/adr-format.mdc`, номер по `ls decisions/` в момент коммита).
- `ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md` — граница платформы и подсистемы (§1 принципы, §4 хуки и их замена, §5–§5b план и ход работ, §6 решения владельца).
- `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` — публичный контракт модуля консоли.
- `ARCHITECTURE.md` — система и история решений; `GLOSSARY.md` — слова проекта.

## Навыки
- `skills/` — навыки проекта (`lesson-spec`, `platform-review`); в `.claude/skills/` символьные ссылки. Правит только «Архитектор» (ADR-0080 доп. 14).

## Правила проектирования (`.cursor/rules/*.mdc`)
- Перед кодом: `service-boundaries.mdc`, `messaging-contracts.mdc`, `resilience.mdc`, `observability.mdc`, `data-consistency.mdc`; класс части определяет `architecture.mdc`.
- Перед запиской: `adr-format.mdc`, `doc-language.mdc`.
- Остальные по теме: `devices-and-media`, `events-and-alarms`, `recording-and-retention`, `sharding-and-backpressure`, `consensus-and-leadership`, `control-and-data-plane`, `plugins-extensibility`.

## Код курса
- `Source/` — единственный код курса: `w2cplatform/` платформа (с `cluster/`, `domain/`, `trust/`), `vms/` подсистемы, `deploy/`, `gstvms/`, `tests/`, `traces/`. Тесты: `tests/run.py`, `tests/cluster/run.py`, `tests/domain/run.py`, `tests/domainvms/run.py` в venv python3.12 с pyyaml, cryptography, pysyncobj; jsdom-тесты модуля в `tests/console`.
- `tests/testdata/testsub*.yaml` и общие таблицы `tests/testdata/*.tsv` — данные спецификации, один YAML с продуктом; их байты правит «Спецификация» (ADR-0080 доп. 16). Она же правит проверки курса над каноном: `tests/console/**`, `tests/test_boundary.py` с `boundary_debt.txt`, `tests/test_console_module.py`, `test_console_page.py` (ADR-0080 доп. (22), (23)).
- Модуль VMS — `VMS/` (ADR-0090): уроки подсистем `VMS/NN-<имя>/`, канон манифестов и оболочек VMS — `VMS/<NN-sub>/<sub>.subsystem.yaml`, `<sub>.shell.html` (доп. (6) п. 8); пишет «Спецификация VMS» по белому списку, хуки `tools/vms-boundary/`. `Source/vms/*` — байты замороженного свидетеля: после старта VMS их не правит никто (доп. (7) п. 4; `check_spec` сверяет `tools/vms-boundary/source-vms.sha256`).
- Новые реализации генерируются по спецификации из общей папки `/Users/murat/w2c/cammeta-specs` (выгрузка спецификации курса, обновляет «Архитектор» `tools/export.sh`): в стадии C — в `cammeta-c-<язык>` (ADR-0083 доп. (22), (23)); прежние `/Users/murat/w2c/cammeta-python`, `cammeta-go` — замороженные свидетели на выгрузке `d27f95d`; старые (`Source/`, `vmssubsystem`) — свидетели (ADR-0080 доп. 16).
- Тест границы `Source/tests/test_boundary.py` с долгом: долг только уменьшается.

## Продукт
- `/Users/murat/w2c/vmssubsystem` (Go, C++), его `CLAUDE.md` указывает сюда же: решения и правила общие.

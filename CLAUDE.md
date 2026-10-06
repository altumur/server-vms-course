# Курс ServerVMS: что читать любой сессии

Этот файл подхватывается автоматически. Он только указывает, где что лежит; содержание в самих файлах.

## Правила для всех сессий
- `СЕССИИ.md` §1 — правила для всех сессий: принципы владельца, вопрос с решением, отчёт «Сборке» о правках продукта, git по файлам (без `-A`, `--amend`, `stash`; worktree на ветку; пушит main курса «Лекции»), одно имя на обеих сторонах, переименование без следов, словарь границы, решение владельца это файл в `decisions/`.
- `СЕССИИ.md` §2–§3 — состав сессий, кто чем владеет, первый промпт каждой.

## Решения и принципы
- `decisions/README.md` — индекс ADR. Прежде чем спорить с решением, найди его номер; новое решение владельца записывает та сессия, которая его услышала (`.cursor/rules/adr-format.mdc`, номер по `ls decisions/` в момент коммита).
- `ГРАНИЦА-ПЛАТФОРМЫ-И-ПОДСИСТЕМЫ.md` — граница платформы и подсистемы (§1 принципы, §4 хуки и их замена, §5–§5b план и ход работ, §6 решения владельца).
- `КОНСОЛЬ-МОДУЛЬ-ПЛАТФОРМЫ.md` — публичный контракт модуля консоли.
- `ARCHITECTURE.md` — система и история решений; `GLOSSARY.md` — слова проекта.

## Правила проектирования (`.cursor/rules/*.mdc`)
- Перед кодом: `service-boundaries.mdc`, `messaging-contracts.mdc`, `resilience.mdc`, `observability.mdc`, `data-consistency.mdc`; класс части определяет `architecture.mdc`.
- Перед запиской: `adr-format.mdc`, `doc-language.mdc`.
- Остальные по теме: `devices-and-media`, `events-and-alarms`, `recording-and-retention`, `sharding-and-backpressure`, `consensus-and-leadership`, `control-and-data-plane`, `plugins-extensibility`.

## Код курса
- `Source/` — единственный код курса: `w2cplatform/` платформа, `vms/` подсистема, `cluster/`, `domain/`, `tests/`, `traces/`. Тесты: `tests/run.py`, `tests/cluster/run.py`, `tests/domain/run.py`, `tests/domainvms/run.py` в venv python3.12 с pyyaml, cryptography, pysyncobj; jsdom-тесты модуля в `tests/console`.
- Спеки `Source/vms/*.subsystem.yaml` и `tests/testdata/testsub*.yaml` — один YAML с продуктом; после сигнала «Лекций» их байты правит только «Паритет».
- Тест границы `Source/tests/test_boundary.py` с долгом: долг только уменьшается.

## Продукт
- `/Users/murat/w2c/vmssubsystem` (Go, C++), его `CLAUDE.md` указывает сюда же: решения и правила общие.

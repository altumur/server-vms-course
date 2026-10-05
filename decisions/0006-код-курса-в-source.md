---
status: accepted
date: 2026-10-04
decision-makers: владелец
consulted: «Архитектор», «Лекции»
informed: «Сборка», «Code-ревью», «Сравнение»
---

# Код курса в одном месте: `vmsserver` → `Source`, старый Go-порт удалён

## Context and Problem Statement
Код курса лежал в трёх местах: `vmsserver/` (М10), `М11_ClusterVMS/clustervms/` и `М12_DomainVMS/domainvms/` как тонкие пакеты поверх него с хаками `sys.path`; рядом лежал старый Go-порт `vmsserver-go` и тест сверки с ним.

## Decision Drivers
* все лекции должны ссылаться в одно место;
* код на Go живёт в продукте, а не в курсе.

## Considered Options
* оставить три пакета и порт;
* `vmsserver/` → `Source/`, кластерный и доменный код переезжают внутрь, порт и `test_cross_go_worker.py` удаляются.

## Decision Outcome
Выбрано второе. Первый коммит чистый `git mv` с правкой ссылок; содержательные переносы (`w2cplatform/cluster`, `w2cplatform/domain` + `vms/domainpart`) отдельными шагами. Переименование идёт первым, до теста границы.

### Consequences
* Good, because один корень на `sys.path`, одна ссылка из уроков.
* Bad, because все записки и скиллы с путями правятся одним заходом; сверка Python с Go теряет свой тест (его заменяет паритет спек и форматов).

### Confirmation
`Source/` единственный каталог кода курса; `vmsserver-go` отсутствует (коммиты 6eb7626, 2cc1aa1); тест «каждый путь из `*.md` существует».

## More Information
Связано: ADR-0007, ADR-0008.

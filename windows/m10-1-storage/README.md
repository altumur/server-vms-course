# Окно Python-хранилища М10/1

Архитектор разрешил интеграцию до C5 в решении
`decisions/inbox/2026-10-14-м10-финальный-diff.md`, commit `9a4fb347`.
Платформа подготовлена в `codex/course-m10-storage`; команда окна в main её
не вливает. Продукт не менялся. Результат, приёмка и оставшиеся действия —
[FINAL.md](FINAL.md); исходная форма и решение о назначении окна — [FORM.md](FORM.md).

## Проверенный код и приёмка

Source checkpoint: `13ca0880472e850f8f76219aab1a377ec06ada09`.
Source tree: `f91530b2ee00853c37072550f8b858fce2716e2d`.
Перенос артефактов после проверки Source не меняет.
Все окончательные коды выхода — 0: unit1071+845, JS40 (суммарно1956/0/0),
Cluster117/0/0, Domain228/0/0, DomainVMS166/0/0;
shared HTTP/File/Mem каждый98/98, target30/0/0.
[checks-pending.json](checks-pending.json) фиксирует полное разбиение unit и команды;
коды выхода сохранены в отдельных `*.exit`.

## Внешний архив и хеши

По ADR-0081 п.2 и решению9a4fb347 логи, сырые ответы приёмки, runtime manifests,
исходные хеши Source и тексты независимых аудитов вынесены из репозитория:

`/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/`

[sha256-manifest.json](/Users/murat/w2c/course-book-merge-evidence/m10-1-storage-e404246b/sha256-manifest.json)
содержит SHA256 всех190 исходных файлов окна на
`e404246b99c18b5e5a67a8b768df5666cdb4e1b4`, включая оригиналы оставленных документов.
SHA256 самого manifest:
`dcd23412819c9d21893250758e65f98a9f05d983afc88f449883802b5bfea34e`.
Копирование каждого файла проверено хешем до удаления из рабочего дерева.

[evidence-locations.json](evidence-locations.json) сохраняет явное соответствие
каждого из189 исторических хешей [evidence-final.json](evidence-final.json):
исходный SHA256, retained/external, внешний snapshot path и остающийся repo path.
61 исходный артефакт retained,128 external; отдельно сохранён исходный
`evidence-final.json`. Для обновлённых README/FINAL исходные версии находятся
в snapshot, актуальные хеши — в `repository_current_files_sha256` этой карты.
Старые evidence manifests остаются историческими снимками, а не утверждением,
что удалённые пути всё ещё существуют в репозитории.

Структура имён во внешнем архиве сохранена: например, окончательные
`unit-pending-part-1.log`, `unit-pending-part-2.log`, `js-pending.log`,
`cluster-pending.log`, `domain-pending.log`, `domainvms-pending.log`;
`acceptance-{http,file,mem}-pending/` содержит точные ответы и вызовы API.
Все соответствующие `*.run.json`, `source-pending.json`, `source-unchanged.json`,
`inputs-pending.json` — там же. Красные диагностические прогоны также сохранены;
они не объявляются зелёной приёмкой.

В репозитории оставлены только README/FORM/FINAL, evidence*.json, checks-*.json,
*.exit и пробы/раннеры *.py, как потребовал Архитектор. Для повторного прогона
используйте отдельный внешний output; новые логи в git не добавлять.

# Как запускались проверки

Python: /Users/murat/w2c/vms-nightly/venv/bin/python (3.12).
Рабочая папка — Source/. OBSD_BIN=/Users/murat/w2c/vms-nightly/exe/obsd,
PYTHONUNBUFFERED=1. W2C_PRODUCT_REF не задан. Unit использует временную
ссылку tests/console/node_modules на зависимости общей папки курса;
после прогонов ссылка удаляется, зависимостей в diff нет.

- Unit первый: штатный tests/run.py без фильтра;1935/0/0, exit0.
  Лог unit-full-first.log/.exit. Он начат до окончательных Device gating
  и ERROR-state исправлений; сам по себе не объявлен проверкой неизменного
  финального runtime. Затронутые пути затем проверены отдельно и повторно
  всем финальным unit ниже.
- Финальный unit: четыре независимых штатных tests/run.py со списками
  unit-partitions.json. Это разбиение всех160 test_*.py ровно по одному
  разу и один console; нет skip/filter по исходу. Каждый процесс имеет
  собственный runroot/временные stores. unit-part-1…4.log/.exit.
  unit-runtime-inputs.json — SHA256 всех runtime файлов до их старта;
  после окончания проверено совпадение. Агрегат и полнота — unit-summary.json.
- Cluster: tests/cluster/run.py; cluster-full.log/.exit.
- Domain: tests/domain/run.py; domain-full.log/.exit.
- DomainVMS: tests/domainvms/run.py; domainvms-full.log/.exit.

До фиксации исправлений также сохранены красные/целевые прогоны:
core-first (файл targeted-first), core-second (targeted-second), core-third,
cluster/domain-full-first, cluster/domain-migration-targeted.
Причины и судьба тестов — CHECKS.md. Внешние helper-логи не используются
вместо интегрированных прогонов этого окна.

Форматы runtime/новые сценарии acceptance М10 не изменялись C4. Полные
наборы здесь проверяют эту реализацию C4; не выдают красный storage baseline
предыдущей пробы за зелёную shared-приёмку. Продукт руками не читался и не
правился; штатный spec_parity автоматически сверяет доступные спеки.

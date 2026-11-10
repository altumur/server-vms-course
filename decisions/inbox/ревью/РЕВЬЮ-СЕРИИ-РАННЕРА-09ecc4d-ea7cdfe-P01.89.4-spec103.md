# P01.89.4: чтение дельты серии раннера `09ecc4d..ea7cdfe` (Спецификация)

Читатель: spec103 (Claude Opus). Ветка `runner/p01-89-offline-build-logmask`, репозиторий `/home/pilot/git/cammeta-acceptance.git`. Дельта: `a5294ea24a1b0ca095c73aba97fc754e2c9cb394` (стенд группы оставляет `-dir`, `-sockets`, `-rights` шаблону `stand.store`) и `ea7cdfe9749e156369d7567bc74bd3207862072a` (`GOENV=off`, `GOTOOLCHAIN=local` по умолчанию, отказ `tables()` на чужом корне Git, тесты). В задаче указано `ea7cdfe63`; такого коммита нет, голова ветки — `ea7cdfe97…`, читал её. Чужих отчётов по серии не читал.

**Итог: Б0 С1 М1.** Флаги у группы и `power_stand` не дублируются и не теряются; раскладка совпадает с P01.86 В1 и `lifecycle.md`. Проверка корня Git другие маршруты не ломает. Единственное С: у базовой группы `-dir` теперь указывает на каталог, которого нет, а норма этот случай не описывает.

## Что прочитано и запущено

- Весь diff `09ecc4d..ea7cdfe`: `runner/store_group.py`, `runner/prepare.py`, `runner/c_vector_packages.py`, тесты `test_store_group`, `test_power_stand`, `test_prepare`, `test_vector_packages_script_mode`.
- Контекст: `store_group.Group` (`directory`, `sockets`, `platform`, `start`, `op`, `restart`), `power_stand.Members` и `JOIN`, `stand.py` (`@foreign`, `@backup … in-data`, создание `{data}`), вызовы `tables()` и драйверы с `later_tables` (`log-mask`, `rid`, `row-check`).
- Нормы: PROFILE «Substitutions» и общий README «Member launch» после P01.86 (`36492fa6f`), `lifecycle.md`, P/01.3 N1.3 (`format`, `-dir`, `recover`, отказы `start_flags`), P/02.4 раскладка `/data/platform/configstore 0700`, сценарии главы 3 и стенда трёх серверов (флаги строк `@store-start`).
- Тесты (свои запуски на архивах ревизий):
  - `ea7cdfe`: `test_prepare` и `test_vector_packages_script_mode` — 45 OK. `StoreGroupProcesses` — всё OK, кроме `test_checker_bridge_retires_owned_children_and_seals_report`, у которого ERROR на обеих ревизиях из-за моей выгрузки. `power_stand.Stand` — всё OK.
  - `09ecc4d` с тестами `ea7cdfe`: падают `test_store_op_arguments_exit_only_and_boundary_b`, `test_default_role_comes_from_chapter_and_as_persists`, `test_real_member_start_restarts_signals_and_mismatched_kit_exit_two`, `test_published_second_member_force_reaches_native_command_in_each_scenario` (×3), `test_the_member_lies_in_the_platform_directory_of_its_server`. Тесты ловят старую раскладку.
  - Тестам групп нужна каноническая выгрузка. Обе выгрузки на машине (`/home/pilot/cammeta-specs`, `…-kit3`) раннер отвергает: root `COURSE_COMMIT`. Я собрал свою: Git-дерево из `Platform` и `VMS` main `36492fa6f` с метками `Platform/COURSE_COMMIT` и `VMS/COURSE_COMMIT`. Плановые тесты `StoreGroupPlan` и `power_stand.Plan` на ней дают ERROR на обеих ревизиях одинаково. Это несовпадение моей выгрузки с ожидаемым срезом, а не дельта.

## Флаги и раскладка

| | Базовая группа | `power_stand` |
|---|---|---|
| `{data}` (= `PLATFORM_DIR` процесса) | `<root>/<id>` | `PLATFORM_DIR` сервера |
| `-dir {data}/configstore` из шаблона | `<root>/<id>/configstore` | `<server>/configstore` (как прежде) |
| `-sockets {rundir}` из шаблона | `<root>/<id>/run` (как прежде) | `<server>/run` (как прежде) |
| `-rights {rights}` из шаблона | файл прав стенда | права, выведенные из манифестов |
| `{dir}` у `store-op` | `store_directory()` = `<root>/<id>/configstore` | то же, `<server>/configstore` |
| дописывает раннер | `-id`, `-tls`, `-api`, `-tuning lan`, голосующему `-raft`, `-raft-bind`, затем слова директивы | то же; слова директив из `JOIN` |

- Дублей нет: из дописываемых флагов ушли ровно `-dir`, `-sockets`, `-rights`; `-max-body`/`-max-value` раннер не дописывал и прежде. Тест считает каждый флаг ровно один раз и сверяет значения `-dir`, `-sockets`, `-rights` с шаблоном.
- Потерь нет: `@restart` повторяет сохранённую команду целиком; `{socket}` остаётся `<…>/run/admin.sock`, по нему же готовность.
- Слова строк `@store-start` в сценариях главы 3 — только `-bootstrap`, `-door`, `-force`, `-group-size`, `-join`, `-voters`. Ни одно не совпадает с флагами шаблона или раннера. `JOIN` у `power_stand` — те же слова.
- Совпадает с нормой: PROFILE «Substitutions» и README «Member launch» (P01.86) — каталог store участника `configstore` его `PLATFORM_DIR`, это же `{dir}`. `lifecycle.md` — `-dir {data}/configstore`. P/01.3 `recover -id -dir` — `store-op` получает тот же `-dir`.

## Проверка корня Git

`tables()` вне маршрута пары перед `git ls-tree` требует, чтобы `git rev-parse --show-toplevel` (через `realpath`) равнялся корню выгрузки, иначе `RunnerError`.
- Срабатывает только у драйверов с поздними таблицами (`vector-log-mask`, `vector-rid`, `vector-row-check`) и только при `root`, не равном `None`.
- Маршрут пары не затронут: в нём `source_git.active()` истинен, ветка не исполняется; строки пары читаются в процессе (`execute_bound` внутри `read_context`).
- Маршрут одного корня работает на checkout выгрузки (подготовка требует чистого `HEAD` на пине). Корень worktree `--show-toplevel` даёт сам, символическая ссылка снимается `realpath`.
- Раньше дерево без `.git` и прежде давало `RunnerError` (`ls-tree` с ненулевым кодом). Новый отказ закрывает только случай «дерево внутри чужого репозитория», на котором я показал молчаливое сужение в P01.89.2 (М3).

## Находки

### С1. Каталог store участника базовой группы не создаётся, а норма об отсутствующем `-dir` молчит

**Код:** `runner/store_group.py:91–103`, `:162`, `:192–195`. **Норма:** P/01.3 N1.3 `format` («the directory is empty → write FORMAT»; непустой без метки — отказ, код 2); P/02.4: на коробке `/data/platform/configstore` с правами `0700` создаёт установщик.

Раньше раннер давал демону группы существующий пустой каталог `<root>/<id>` как `-dir`. Теперь `-dir` — `<root>/<id>/configstore`, а раннер создаёт только `<root>/<id>` (и `run/` создаёт сам демон). `power_stand.Members.directory()` каталог `<server>/configstore` создаёт. Стенд одного store (`stand.py:147`, `:493`) создаёт только `{data}`: там поведение прежнее и тоже держится на демоне.

Норма описывает пустой каталог, отсутствующий — нет. Реализация, которая по раскладке установщика считает отсутствующий `-dir` ошибкой старта, законна, но теперь не поднимет группу. Раньше поднимала: это регресс дельты для базовой группы. Тесты этого не видят: поддельный store сам делает `mkdir` своего `-dir`.

**Исправление (нужно слово Архитектора, смысл новый):**
- либо стенд создаёт пустой `{data}/configstore` с `0700` перед первым стартом во всех трёх стендах (одного store, группы, трёх серверов), как установщик на коробке, — тогда я допишу это в общий README «One data directory»;
- либо норма P/01.3 N1.3 `format` говорит, что демон создаёт отсутствующий `-dir`.

Рекомендую первое: продукт не получает нового обязательства, стенд повторяет раскладку P/02.4. Тест: поддельный store, который отвергает отсутствующий `-dir`.

### М1. Номер коммита в задаче

В задаче и строке очереди стоит `ea7cdfe63`; в репозитории такого коммита нет, голова ветки — `ea7cdfe9749e…`. Читал голову ветки. Для пина раннера под P01.88 стоит назвать полный SHA.

## Окружение `build`/`unit` для нормы

Итоговое окружение `build_environment()` на `ea7cdfe`:
- `command_environment()`;
- присутствующие у вызывающего `GOMODCACHE`, `GOCACHE`, `GOPATH`, `GOFLAGS`, `GOTOOLCHAIN`, `GOSUMDB`;
- всегда `GOPROXY=off` и `GOENV=off`;
- `GOTOOLCHAIN=local`, если вызывающий его не задал.

`invoke()` проверяющих и процессы стенда идут с `command_environment()` без `GO*`. Это совпадает с формулировкой задачи. Текст PROFILE из P01.86 (без `GOENV` и умолчания `GOTOOLCHAIN`) этим же коммитом приведён к коду, EN и RU; M1 и M2 моего чтения P01.89.2 закрыты в коде.

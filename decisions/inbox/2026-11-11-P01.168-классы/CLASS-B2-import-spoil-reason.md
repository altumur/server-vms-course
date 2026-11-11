# B2 — `@import store` и `@spoil row` не исполняются: движок ставит закрытые причины R030 без их условия

**Случаев:** 57 шагов `not_executed` цели P/01.3/daemon (`Platform/01-store/acceptance/3/scenarios.tsv`):
- `stage_package_not_exported` — 43: сц. 11-copy стр. 38–48 (11 шагов, первый `@import store inputs/copy-ok.jsonl`), сц. 12-copy-refused стр. 49–80 (32 шага, первый `@import store inputs/bad-format.jsonl`);
- `store_spoil_row_missing` — 14: сц. 20-spoil-row стр. 185–192 (8, первый `@spoil row testsub/counters/s1`), сц. 22-spoil-row-guard стр. 198–203 (6, первый `@spoil row testsub/counters/s3`).

Это открытый вопрос P01.188 («43 шага `stage_package_not_exported` — движок или норма»).

## Наблюдение движка
`engine.json`: у директивы и у всех шагов сценария после неё `result: not_executed`, `reason` — `stage_package_not_exported` или `store_spoil_row_missing`.

**Повтор replay188** (`replay188/trace/P_01_3_daemon.jsonl`; итоги совпали с диагностикой). На `acceptance/3/scenarios.tsv:38` движок «отправил» `@import store inputs/copy-ok.jsonl`, на `:49` — `@import store inputs/bad-format.jsonl`, на `:185` — `@spoil row testsub/counters/s1`, на `:198` — `@spoil row testsub/counters/s3`. Это только текст директивы: статуса и тела нет, процесса по директиве движок не запускал. Шаги `:39`–`:48`, `:50`–`:80`, `:186`–`:192`, `:199`–`:203` не отправлены совсем (запроса в трассе нет). Повтор поведения кандидата на этих 57 шагах не охватывает.

**Поправка к прежней записи «команды не вызывались».** По директиве не вызывались. Но один раз на цель обе команды вызвал движок, вне сценария: это разовая проба интерфейсов стенда (`internal/engine/run.go:243–291` → `executeStand`, `run_stand.go:96–129`). Цель P/01.3/daemon требует `stand.store`, `stand.backup`, `stand.import` (`targets.tsv:6`), а `stand.spoil-row` добавляется условием `row_spoil` (`run.go:361–370`). Подстановки — постоянные `standValues` (`run_stand.go:170–200`), а не из директив. stderr демонов цели (`replay188/stderr/P_01_3_daemon.txt`) показывает их итоги:
- `the data directory is owned by a live daemon` — `stand.spoil-row`: `./bin/configstore-tool spoil-row {data} {key} {what}` с `{data}` = каталог данных **живого** стора стенда, `{key}` = `acceptance/key`, `{what}` = `body`. Кандидат (`cmd/configstore-tool/adapters.go:156–166`) берёт `flock` на `{data}/configstore` (`internal/datadir/datadir.go:35–48`), стор держит его — `ErrOwned`, код 1. По `README.md:293` движок сначала останавливает стор (SIGTERM), здесь он этого не сделал;
- `configstore: refused: no_leader: dial unix /run/configstore/admin.sock: connect: no such file or directory` — `stand.import`: `./bin/configstore import --from {file} -dir {data}/configstore -index-base {index_base}` с `{file}` = `<tmp>/import.jsonl` (пустой, `run_stand.go:147–151`), `{data}` = тот же каталог живого стора, `{index_base}` = `0`. Кандидат (`internal/daemon/cli.go:266–281`) видит, что каталог занят живым демоном, и передаёт импорт лидеру через `admin.sock`. Флага `-sockets` в шаблоне профиля нет, поэтому сокет берётся по умолчанию, `/run/configstore/admin.sock` — его в песочнице нет, отказ `no_leader`. По `README.md:299` движок даёт `import` новый пустой `{data}` остановленного стора, здесь это не так;
- `configstore: refused: no_leader: dial unix …/acceptance-engine-3079327592/run/admin.sock` — `stand.backup` до готовности стора (см. B1).

Итоги этих проб движок пишет только в журнал вызовов (`run_stand.go:123–128`), на вердикт шагов они не влияют. Все три отказа кандидата верны при поданных предусловиях.

Код движка `ef7dcf9`:
- `internal/engine/scenario_verdict.go:232–254`, `directiveReason`: `@spoil` → `store_spoil_row_missing`, `@rights` → `store_rights_template`, `@import` → `stage_package_not_exported`. Всё безусловно, флаг `missing = true` — профиль и стенд не проверяются;
- `:125–144` — до этого `executeScenarioDirective` (`run_directives.go:14–49`) не знает `@import` и `@spoil`;
- `:258–276`, `abortingDirective`: `@import store` и `@spoil row` обрывают сценарий, а `:136–142` переносит причину директивы на все следующие шаги;
- сопутствующий дефект для будущей правки: `run_stand.go:196–198` подставляет в `stand.spoil-row` постоянные `{key} = acceptance/key` и `{what} = body`, а не ключ и вид из директивы. Проба spoil-row выше шла с этими же постоянными (`run_stand.go:196–198`); в stderr ключа нет, его видно только по коду.

**Откуда слово.** Закрытый словарь пришёл из прежнего раннера курса (опись P01.28.4, п. 6.21, `decisions/inbox/2026-11-09-P01.28.4-опись-скрытых-норм-раннера-4.md:121`). Там `stage_package_not_exported` значило «the pinned export does not publish this stage package (forms/ of ADR-0124)» (`wt-review103-runner838-base/runner/scenario_status.py:7`). Ставилось оно целиком на цель, исходные файлы пакета которой отсутствуют в выгрузке (`c_targets.py:627–635`), а не на шаг `@import`. `store_spoil_row_missing` там — «01-store.stand.spoil-row is missing».

## Норма
J-вход `49e62279`:
- `common/acceptance/spec/acceptance.norms.md:61` (P/AC-R030) — «The reason of a `not_executed` result is one of the closed list: … `store_rights_template`, `store_spoil_row_missing`, `stage_package_not_exported`; …». Для этих трёх слов, в отличие от соседних (`installer_ceiling_unproven`, `installer_rights_check_missing`, `no_machine_form`, `MissingBinding`), условие не написано;
- `common/acceptance/README.md:293` — для `store_spoil_row_missing` условие есть, но в словаре директив: «there is no command — not_executed only for a scenario with `@spoil row`». Для `stage_package_not_exported` условия нет нигде в J;
- `common/acceptance/README.md:299` — `@import store <file>`: «the runner takes a new empty `{data}`, calls the command `import` of «Stand» with `{index_base}` … then … starts a second store instance … its door is `restored`. The expectation `ok` — the code of `import` is 0; `refused` — code ≠ 0»;
- `common/acceptance/forms/targets.tsv:6` — цель P/01.3/daemon требует `stand.store`, `stand.backup`, `stand.import`, а `stand.spoil-row` — при условии `row_spoil`.

## Код кандидата
Профиль `01-store/acceptance.yaml`: `:11` `import: ./bin/configstore import --from {file} -dir {data}/configstore -index-base {index_base}`, `:13` `spoil-row: ./bin/configstore-tool spoil-row {data} {key} {what}`. Обе команды объявлены, значит условие `store_spoil_row_missing` («there is no command») ложно. По чтению кода:
- `internal/daemon/cli.go:266–285` (`cliImport`) и `:297–320` (`importBox`): каталог создаётся, берётся во владение (`flock`), импорт идёт через `copycore`, отказ — код по каталогу отказов;
- `cmd/configstore-tool/adapters.go:156–178` (`spoilRow`): `{data}/configstore`, `flock`, `durable.Store.Spoil(key, what)` (`internal/durable/store.go:261`).

Повтор показал только ветки отказа обеих команд на занятом каталоге (пробы стенда выше): `spoil-row` — `ErrOwned`, `import` — передача живому лидеру и `no_leader`. Проходит ли кандидат сц. 11, 12, 20, 22 (импорт в свежий `{data}`, порча строки на остановленном сторе), **не повторено**: replay188 их не охватывает, движок директивы не исполняет.

## Что видела модель
`README.md:293`, `:299` в M те же. Модель видела их в выводе вызова 31 (обрезка 900 знаков на строку) и прочла `acceptance/3/README.md` целиком (вызов 33). `acceptance.norms.md` (R030) в M нет — это норма судьи. Догадок нет. На поведение кандидата класс не влияет.

## Мнение
Исход — **движок**: при объявленных `stand.import` и `stand.spoil-row` директивы по `README.md:293`, `:299` исполняются. Повтор мнение не меняет. Он добавляет второй дефект движка без влияния на вердикт: разовая проба `stand.import` и `stand.spoil-row` идёт на каталоге живого стора, вопреки предусловиям `README.md:293` (стор остановлен) и `:299` (новый пустой `{data}`). Вторая причина — **норма**: R030 перечисляет `store_rights_template`, `store_spoil_row_missing`, `stage_package_not_exported` без условий. Модель линии судьи подставила `stage_package_not_exported` на `@import` по одному созвучию. Третья — **цикл** линии судьи: ворота не подавали сценарий с `@import`/`@spoil` на заглушку с этими командами.

Предложения:
- правка нормы R030: к каждому слову — его условие. Для `store_spoil_row_missing` — «the profile has no `stand.spoil-row` and the scenario has `@spoil row`/`row-index`». Для `store_rights_template` — по `PROFILE.md`. Для `stage_package_not_exported` — условие прежнего раннера, если слово ещё нужно; иначе слово убрать;
- ворота линии судьи: заглушка с `stand.import`/`stand.spoil-row` получает вызов команды с `{file}`, `{index_base}`, `{key}`, `{what}` из директивы. Причина `not_executed` из этой тройки при объявленной команде — red ворот.

## Вопросы ревьюеру
1. Нужно ли `stage_package_not_exported` в R030 после ADR-0124/ADR-0133, если J-вход публикует все пакеты целей? Или слово убрать, а не уточнять?
2. Достаточно ли условия `README.md:293` в словаре директив, или его надо повторить в R030, чтобы список был закрыт и с условиями?

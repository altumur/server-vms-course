# tools/normgen — генераторы кода по формам (ADR-0120 п. 2 (а), ADR-0125, ADR-0126)

Генераторы строят механическую часть урока из машинных форм без модели; у каждого — свой внешний судья
(ADR-0125 доп. (1) п. 1). Генераторы — Python stdlib; выход — Go 1.22, только stdlib.

| № | Генератор | Форма | Выход (`out/p01-1/go/`) | Часть пакета | Судья |
|---|---|---|---|---|---|
| 1 | `gen_checks.py` | `forms/write-checks.tsv` | `checks/` (+ `python/checks.py`) | `writecheck` (с `kit/go`) | оракул `check_tables` (`test_gen_checks.py`) |
| 2 | `gen_door.py` | `spec/01-store.api.openapi.yaml` | `door/` | `door` | раннер P/01.1 на заглушке `kit/build_stub.py` → `door_judge.py` |
| 3 | `gen_flags.py` | `forms/daemon-flags.tsv` | `flags/` | `flags` | `flag_judge.py` — пробы запуска демона |
| 3 (P/02) | `gen_flags.py --lesson 02-installer` | `forms/operator-commands.tsv` (команда, процесс, префикс argv, позиционные — JSON Schema массива строк) и `forms/daemon-flags.tsv` (опции команд: string, number, file, bool; CEL над f и cmd) | `flags/` — `ParseArgv(process, argv)`, `Lookup`, `Parse`, `Commands`; отказ без кода выхода (код — у команды по refusals.tsv); написание опций и десятичная запись number — выбор пакета | `flags` | `cmdflag_judge.py` (своя модель форм, оракул CEL; мутанты — `test_gen_flags_cmd.py`) |
| 4 | `gen_refusals.py` | `forms/refusals.tsv` | `refusals/` | `refusals` | `refusal_judge.py` — приёмка и `door.Refuse` |
| 4 (P/02) | `gen_refusals.py --lesson 02-installer` | `forms/refusals.tsv` на 15 колонок (урок без двери: surface call/cli/start/process/peer, code exit N / exit !0 / NNN у peer / -, word, log) — только закрытые колонки, проза cause/outcome/diagnostic/caller в код не идёт | `refusals/` — `Spec{Exit, AnyNonZero, Status, Word, Log, Words}`, `ExitCode()` (1 за «exit !0» — выбор пакета) | `refusals` | `refusal_judge.py` (каталог против таблицы; каждое `exit N` шага RUN швов — в каталоге; мутанты — `test_gen_refusals_plain.py`) |
| 5 | `gen_families.py` | `common/data/catalog.tsv`, `01-store/data/<семья>.schema.json` (+ `layers.tsv` — сверка со схемой, `outcomes.tsv` — только путь, читатель, приоритет, единица), плейсхолдеры `common/data/README.md` | `families/` (`families.go`; ручная среда `famrt/go/runtime.go` — проход стека В7) | `families` | `family_judge.py` — векторы `common/vectors/family-read/01.tsv` и `--v7` свои экземпляры против стека В7 курса; `check_spec` — векторы против В7 |
| 6 | `gen_tests.py` (+ `common_vectors.py`) | `vectors/jcs`, `vectors/rights-evaluator`, `forms/stages.tsv`; общие пакеты урока `common/vectors/<пакет>` (состав — объявление `COMPOSITION`, до формы consumers.tsv; P/01: crl, revoked, log-mask `cases.tsv`, store-client, family-read `01.tsv`) | `vectortests/` (`TestCommon<Пакет>_Line<N>`), `vectorcmd/` (ветви пакетов; family-read — частью `families`, без кода модели), `vectoradapter/` (`canonical.go`, `rights.go`, `crl.go`, `revoked.go`, `logmask.go`, `storeclient.go` — заглушки реализации по файлу на функцию) | `vectors` (на уроке с family-read нужна `families`) | `vector_judge.py`, раннер `P/NN/vectors-<пакет>` |
| 2 + 3 | `gen_launch.py` | `forms/daemon-flags.tsv`, OpenAPI (через части `flags`, `door`) | `launch/`, `frame/` (рамка HTTP — **реализации**, временная на net/http, якоря Н2.1 в шапке), `cmd/configstore/` | `launch` (нужны `door`, `flags`, `stagetests`, `admin`) | раннер P/01.1 на пакете как есть (пустое ядро `launch.Empty` на заглушке `coreadapter.Open`) → `launch_judge.py` (этап `launch`: `01-absent`) |
| 3 + Н1.3 | `gen_admin.py` | `forms/daemon-flags.tsv` (подкоманды — колонка commands), `spec/01.3-store.norms.md` (блок Н1.3 R006: admin_ops, copy, import, floor, box, repeat; R018; Н3 «recover»), `forms/refusals.tsv`, общий README приёмки (`@spoil row`) | `admin/` — `admin.go` закрыт (`Env`, `Run`, `NotInStage` — exit 1), по файлу на подкоманду и `own.go` (свои команды профиля: `spoil-row`) — **реализации**, кладутся один раз; `launch`: `App.Admin` nil → `admin.Run`, `admin.Own` — до разбора флагов | `admin` (нужна `flags`; её требует `launch`) | `admin_judge.py` (подкоманда без реализации — «not in this stage» exit 1, флаг вне формы и чужой команды — 2, `spoil-row` — 1) и `test_gen_admin.py` (якоря, мутанты, `--seed`) |
| stagetests (P/02) | `gen_cmdtests.py --lesson 02-installer` | `forms/stages.tsv` (gate `tests:2.K:…:seams`, `verdicts:2.1:*`; `puts:` — excluded «needs the store of P/01 (runner corpus puts)», решение «Архитектора»), `acceptance/K/seams.tsv` (RUN, CALL command/load/load-catalogue/rollout-poll, @file, @read, @parallel — `forms/README.md` урока), `acceptance/1/verdicts.tsv` + `cases/` + `classes.tsv` | `stagetests/` (движок не по HTTP, `Test<Этап>_<Сценарий>`, `Test<Этап>_Verdicts`, `testdata/verdicts.jsonl` — случаи base64, `inventory.tsv`), `lessonadapter/` (`lessonadapter.go` — типы, закрыт; `command.go`, `load.go`, `catalogue.go`, `poll.go` — **реализации**) | `stagetests` | `test_gen_cmdtests.py` (заглушка — красное без паники; подставной адаптер — зелёное; мутанты адаптера и шва) |
| 2 + Н3 | `gen_core.py` | `apidoor.Handler` (выход `gen_door`), `spec/01.1-store.norms.md` (якоря req разделов Н3, Н2.1; над `Context` — места личности: якоря P/01.2 Н1.1, Н3 «check», P/01.1 R050, R066, порядок P/01.3-07, заголовок, строки 403 `refusals.tsv`; над методами глав 1.2/1.3 — пункты Н2 норм 1.2/1.3, строка таблицы дверей P/01.3-R016 и строки `refusals.tsv` двери) | `out/p01-1/core/coreadapter/` (`core.go`, `open.go` и по файлу на метод `apidoor.Handler` — **реализации**, кладутся один раз; заглушка не кладётся, если её имя уже объявлено в пакете) | `core` (нужны `door`, `stagetests`) | `test_gen_core.py` (сборка, заглушки, тесты этапов красные без паники) и раннер на пакете (этап `launch` остаётся закрытым: `Get` заглушки — пустое хранилище) |

Ручное — один раз на словарь: среда CEL `runtime/`, примитивы `#fn` `prims/` (Go и Python), типы флагов
`flags/go/flagtypes.go`, среда двери `doorrt/`, пакет `kit/go` (`jsonstrict`, `writecheck`).

## Пакет Б

`python3 kit/build_kit.py <dst> --module <путь импорта <dst>/01-store> [--part door] [--part flags] [--part refusals]
[--part tests]` — части в `<dst>/01-store/internal/`, `KIT.md` и `kit.manifest.json` (`parts`, строки по
происхождению и части, `provenance` — по каждой части sha256 форм, генератора, ручной среды и судьи, `output` —
sha256 набора её файлов, `judged` — ссылка на суд этого выхода, `--judged часть=ссылка`). Каждый копируемый выход
сверяется со свежим прогоном своего генератора (№ 1, № 2 — тоже, не по шапке): отставший от формы, генератора или
ручной среды — отказ сборки, сначала перегенерировать.

KIT.md — справка подключения (ADR-0083 доп. (95) п. 2): сигнатуры частей, по примеру подключения на часть
(`kit/examples/<часть>.go` дословно; `test_gen_launch.py` собирает их в пакете) и экспортируемые имена каждого пакета
(по исходникам). Справка идёт в голову задания вместо тела сгенерированного кода.

## Тесты и судьи — на Linux (CT 103)

Тесты normgen и судьи идут на Linux, на CT 103 (пользователь `pilot`), не на маке: Go 1.22 на macOS собирает с
примитивом `loopback` (пакет `net`) бинарь, который падает в dyld (нет `LC_UUID`).

- Python с `cel_expr_python` (оракул CEL для `test_gen_checks.py` и `flag_judge.py`) — `/opt/check-env/lesson-spec/bin/python`.
- Набор: `test_gen_checks.py`, `test_gen_tests.py`, `test_gen_door.py`, `test_gen_flags.py`, `test_gen_refusals.py`,
  `test_gen_stagetests.py`, `test_gate.py`, `test_judges.py`, `test_gen_launch.py`, `test_gen_core.py`, `test_gen_families.py`, `test_gen_admin.py`, `test_lesson.py`, `test_gen_flags_cmd.py`, `test_gen_refusals_plain.py`, `test_gen_cmdtests.py`, `kit/test_kit.py`, `kit/test_export.py`; затем `skills/lesson-spec/scripts/check_spec.py`.
- Урок (ADR-0125 доп. (5) п. 2): `lesson.py` — `--lesson NN-<имя>` у каждого генератора, судьи и `build_kit` (или
  `NORMGEN_LESSON`; по умолчанию `01-store`): пути урока, out (`out/p01-1` у P/01, `out/pNN` у прочих), модуль Go,
  каталог и модуль пакета (`--module` по умолчанию из урока), нормы по главам. Объявления мест, сделанные для P/01
  (`gen_core`, `gen_admin`, `gen_launch`, `gen_tests`), на другом уроке — отказ с именем урока; P/01 собирается байт
  в байт как до обобщения.
- Пакет попытки — только `build_kit.py <kit> --module … --part … --export <sha выгрузки>`: входы — `Platform/` выгрузки из git
  `cammeta-specs` (`--specs`), код — чистый HEAD курса (правки в `tools/normgen` — отказ); `out` перегоняется во
  временном каталоге, дерево курса не меняется; в `kit.manifest.json` — `commit` и `export`, `SOURCE.txt` пишется сам.
- Посев (код прошлой попытки) — ещё `--seed <work посева>`: цикл копирует пакет поверх посева целиком, поэтому своё
  реализации (editable) идёт в пакет, только если в посеве файла нет или он байт в байт тот, что положил прежний пакет
  (`kit.manifest.json` посева); код модели в пакет не идёт — манифест `seed`: `kept`, `refreshed`.
- `gate.py` — общий разбор списка `gate` формы stages.tsv для генераторов (грамматика шапки формы, как у `check_forms`).
- Судьи: отсутствие исполнения — отрицательный исход. Ожидаемый набор шагов — из сценариев и проекции, не из отчёта;
  шаг без исхода, пустой или обрезанный отчёт, незавершённый `go test` — провал. Запуск демона у `flag_judge.py` —
  готовность (`admin.sock` в `-sockets`); группа без соседей без готовности — «не проверено» с причиной.
- `flag_judge.py --cmd <демон> [--stub] [--box]` — `--stub` для заглушки `flags/stub` (сверка значений), `--box` для
  сборки без raft. Пробы пишут только во временный каталог.
- Судья двери — раннер через очередь CT 103 (`/srv/cammeta-checks`, `check.py submit --env go --with-git`): во входе
  `RUN.py`, раннер, клон выгрузки на коммите `--spec-version` и каталог `build_stub.py` как репозиторий Git; итог —
  `door_judge.py <out/report>`.
- Судья части `launch`: `launch_judge.py job <вход> --spec-version <SHA>` → очередь (`check.py submit … -- python3.12 RUN.py`)
  → `launch_judge.py judge <out/report>`.

# tools/normgen — генераторы кода по формам (ADR-0120 п. 2 (а), ADR-0125, ADR-0126)

Генераторы строят механическую часть урока из машинных форм без модели; у каждого — свой внешний судья
(ADR-0125 доп. (1) п. 1). Генераторы — Python stdlib; выход — Go 1.22, только stdlib.

| № | Генератор | Форма | Выход (`out/p01-1/go/`) | Часть пакета | Судья |
|---|---|---|---|---|---|
| 1 | `gen_checks.py` | `forms/write-checks.tsv` | `checks/` (+ `python/checks.py`) | `writecheck` (с `kit/go`) | оракул `check_tables` (`test_gen_checks.py`) |
| 2 | `gen_door.py` | `spec/01-store.api.openapi.yaml` | `door/` | `door` | раннер P/01.1 на заглушке `kit/build_stub.py` → `door_judge.py` |
| 3 | `gen_flags.py` | `forms/daemon-flags.tsv` | `flags/` | `flags` | `flag_judge.py` — пробы запуска демона |
| 4 | `gen_refusals.py` | `forms/refusals.tsv` | `refusals/` | `refusals` | `refusal_judge.py` — приёмка и `door.Refuse` |
| 6 | `gen_tests.py` | `vectors/jcs`, `vectors/rights-evaluator`, `forms/stages.tsv` | `vectortests/`, `vectorcmd/`, `vectoradapter/` | `tests` | `vector_judge.py` |

Ручное — один раз на словарь: среда CEL `runtime/`, примитивы `#fn` `prims/` (Go и Python), типы флагов
`flags/go/flagtypes.go`, среда двери `doorrt/`, пакет `kit/go` (`jsonstrict`, `writecheck`).

## Пакет Б

`python3 kit/build_kit.py <dst> --module <путь импорта <dst>/01-store> [--part door] [--part flags] [--part refusals]
[--part tests]` — части в `<dst>/01-store/internal/`, `KIT.md` и `kit.manifest.json` (`parts`, строки по
происхождению и части, `provenance` — sha256 формы, генератора и судьи). Выход генератора, отставший от формы, —
отказ сборки: сначала перегенерировать.

## Тесты и судьи — на Linux (CT 103)

Тесты normgen и судьи идут на Linux, на CT 103 (пользователь `pilot`), не на маке: Go 1.22 на macOS собирает с
примитивом `loopback` (пакет `net`) бинарь, который падает в dyld (нет `LC_UUID`).

- Python с `cel_expr_python` (оракул CEL для `test_gen_checks.py` и `flag_judge.py`) — `/opt/check-env/lesson-spec/bin/python`.
- Набор: `test_gen_checks.py`, `test_gen_tests.py`, `test_gen_door.py`, `test_gen_flags.py`, `test_gen_refusals.py`,
  `kit/test_kit.py`; затем `skills/lesson-spec/scripts/check_spec.py`.
- `flag_judge.py --cmd <демон> [--stub] [--box]` — `--stub` для заглушки `flags/stub` (сверка значений), `--box` для
  сборки без raft. Пробы пишут только во временный каталог.
- Судья двери — раннер через очередь CT 103 (`/srv/cammeta-checks`, `check.py submit --env go --with-git`): во входе
  `RUN.py`, раннер, клон выгрузки на коммите `--spec-version` и каталог `build_stub.py` как репозиторий Git; итог —
  `door_judge.py <out/report>`.

# Пробы пятнадцатого ревью: закрытое разделение платформы и подсистемы

Снимки: курс `2f90fbd5`, продукт `c86571d`; снимки «до» для повтора 14-го — курс `e7443379`, продукт `2d46e95`. Правило ADR-0052: пробы лежат в репозитории, их повторяет следующий проход и ночной прогон (Go-половина). Ни одна проба не меняет дерево, которое проверяет: Go-файлы копируются в пакет **копии** дерева (`git archive` в scratch), не в checkout.

## Запуск

Python-пробы берут корень курса (`<снимок>/Source`) первым аргументом или переменной `COURSE_SOURCE`; интерпретатор с `pyyaml`, `cryptography`, `pysyncobj` (python 3.12):

```bash
python РЕВЬЮ-SERVERVMS-15/probes/platform-course/probe_loader_fields.py <снимок курса>/Source
```

Go-пробы — файлы `*_test.go` пакета `w2cplatform_test` (или внутренние `*_internal_test.go`): скопировать в `vmsworker/w2cplatform/` копии продукта и запустить из её корня с курсом рядом:

```bash
W2C_COURSE_DIR=<снимок курса> PROBE15_DIR=<этот каталог>/product/loader go test ./vmsworker/w2cplatform/ -run 'TestProbe15|TestR14|TestProbe'
```

| Каталог | Что проверяет | Курс | Продукт |
|---|---|---|---|
| `platform-course/` | загрузчик курса не сверяет с `fields:` девять ключей (major 1); последствия: держание по опечатке, производная строка, права на строку | `probe_loader_fields.py`, `probe_holds_unitof_typo.py`, `probe_derived_typo.py` (`.out` рядом) | то же место: `unit.go`, `holds.go` — проба Go не писалась, дефект виден кодом |
| `vms-course/` | форвардер: смерть потоков на одном отказе хранилища (blocker), нули в биении (major 3); jobs подаёт мимо двери (major 4); `free-*` в `fetched` (minor 5); слова журнала (minor 6) | `p1`…`p6` с `_env.py` (корень курса аргументом или `COURSE_SOURCE`) | — |
| `product/loader/` | 70 мутаций курсового `testsub2` через оба загрузчика: 20 расхождений (major 6–8, minor 15, 16); дамп дерева ключей; заслонение маршрутов консоли таблицей | `mutate.py`, `mutate2.py` (порождают `cases_*/` из `<курс>/Source/tests/testdata/testsub2.subsystem.yaml`), `course_verdicts.py` → `course_verdicts*.tsv` | `zz_probe15_loader_test.go` → `product_verdicts*.tsv`; `zz_probe15_speckeys_internal_test.go` → `product_keys.txt`; `zz_probe15_shadow_test.go` → `shadow_probe_output.txt` |
| `rerun14/` | копии проб 14-го, потерявших предмет из-за ADR-0060 (учёт человека в `<sub>/asked/`), с поправкой на новый ключ учёта; скрипты запуска всех проб 14-го на четырёх снимках | `door_requests_course_after.py`, `run_py.sh`, `run_loader.sh` | `door_probe_after_test.go`, `r14_filings_platform_after_test.go`, `marks_probe_after_test.go`, `run_go.sh` |

Логи повтора 14-го на снимках «до» и «после» — `../logs/rerun14-*.log`. Ожидаемые результаты на снимках ревью — в `РЕВЬЮ-SERVERVMS-15.md`, колонки «курс / продукт». Проба, которая на новом снимке даёт другой результат, — повод перечитать соответствующую находку.

Скрипты `run_*.sh` в `rerun14/` держат пути снимков в переменных в начале файла — поправьте их на свои копии.

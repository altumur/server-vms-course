# Пробы четырнадцатого ревью: семейство `requests` и базовый воркер

Снимки: курс `e7443379`, продукт `2d46e95`. Правило ADR-0052: пробы лежат в репозитории, их повторяет следующий проход и ночной прогон (Go-половина). Ни одна проба не меняет дерево, которое проверяет.

## Запуск

Python-пробы берут корень курса (`<checkout>/Source`) первым аргументом и запускаются интерпретатором с `pyyaml`, `cryptography`, `pysyncobj`:

```bash
python РЕВЬЮ-SERVERVMS-14/probes/door/door_requests_course.py Source
```

Go-пробы — файлы `*_test.go` пакета `w2cplatform_test` (у `filings` ещё и `vms`). Они подкладываются в дерево продукта через `go test -overlay`, чтобы его не править. Файлы `overlay*.json` рядом с пробами содержат **абсолютные пути снимка ревью**: перед запуском поправьте их на свой checkout или просто скопируйте `*_test.go` в `vmsworker/w2cplatform/` (и `r14_filings_vms_test.go` в `vmsworker/vms/`) и запустите `go test -run 'TestR14|TestProbe' ./vmsworker/...`.

| Каталог | Что проверяет | Курс | Продукт |
|---|---|---|---|
| `door/` | дверь просьб: учёт на человека, idem-ключ, имена `rid`, чужая просьба под тем же `rid` | `door_requests_course.py` | `go/door_probe_test.go` (`TestR14Door*`) |
| `marks/` | метки и жнец (ADR-0054): гонки закрывающего и держателя на пяти хранилищах, пути держателя, права М11 | `p_marks_race_closer_vs_holder.py`, `p_marks_holder_paths.py`, `p_marks_m11_rights.py` | `go/marks_probe_test.go` (`TestProbe*`), `go/run_marks_probe.sh` |
| `filings/` | подача просьб воркером: штампы, повтор, конфликт, пространство `rid`, загрузчик `worker.requests` | `p_r14_filings_course.py`, `p_r14_rid_namespace_course.py`, `p_r14_worker_requests_loader_course.py` | `go/r14_filings_platform_test.go`, `go/r14_filings_vms_test.go` (`TestR14*`) |
| `base/` | базовый воркер: взятие строгого места по чужим часам, помощник сверки, `lost_to_epoch`, `Backoff` | `b1_restart_failures_wiped.py`, `b3_take_epoch_after_lost.py`, `b4_claim_hold_by_foreign_clock.py`, `b5_backoff_constructor.py` | `go/b1_*`, `go/b3_*`, `go/b4_*` (`TestProbeB*`) |
| `loader/` | загрузчик спек: 89 мутированных спек через оба загрузчика, разбор YAML, дубликаты ключей | `probe_spec_loaders.py <курс> <продукт> <specload>`, `probe_yaml_alike.py` | `go/specload/`, `go/yamldump/` (сборка через `go/go.work`, путь поправить), `go/probe_yaml_silent_test.go` |

Ожидаемые результаты на снимках ревью — в `РЕВЬЮ-SERVERVMS-14.md`, колонки «курс / продукт». Проба, которая на новом снимке даёт другой результат, — повод перечитать соответствующую находку.

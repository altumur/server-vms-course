# SUT эталона: сверка раннера до реализаций (PLAN-TRANSITION п. 3.4)

Программа `sut.py` отвечает раннеру `cammeta-acceptance` тем же протоколом, что реализации. Это стенд P/02.1–2.2 и
единая команда пакетов векторов. Бэкендов два:

- `v7` — стек В7 навыка на стандартных файлах выгрузки;
- `dialect` — код навыка по метке `dialect-reference-dc94d0fd1` на файлах диалекта метки; входы и таблицы — из выгрузки.

Ожидание: `v7` даёт все строки таблиц. `dialect` даёт все, кроме дельт набора Б: `v7/out/setb/deltas.tsv`, случаи
`cases.tsv` с иным `ref` и сужения `yts-refusals.tsv`.

## Запуск

```sh
# окружение: стенд В7 (v7/requirements.txt) — jsonschema 4.26.0, ruamel.yaml 0.19.1, cel-expr-python 0.1.3
git worktree add ../wt-dialect-reference dialect-reference-dc94d0fd1           # бэкенд dialect, один раз
PY=/Users/murat/w2c/v7-stand/venv/bin/python
SUT=skills/lesson-spec/scripts/v7/sut/sut.py
SPECS=/Users/murat/w2c/cammeta-specs                                            # выгрузка с пакетом п. 2

$PY $SUT --backend v7 --specs $SPECS selftest            # все таблицы через бэкенд; код 0 — расхождений вне дельт Б нет
$PY $SUT --backend v7 --specs $SPECS materialize /tmp/sut-v7          # каталог реализации для раннера
$PY $SUT --backend dialect --specs $SPECS --dialect-root ../wt-dialect-reference materialize /tmp/sut-dialect
python3.12 runner/all.py --impl /tmp/sut-v7 --only P/02 …                 # из cammeta-acceptance, CAMMETA_SPECS=$SPECS
```

`materialize` создаёт git-репозиторий реализации:
- `SPEC_VERSION` — HEAD выгрузки;
- `assembly.yaml` — один модуль `02-installer`;
- `02-installer/acceptance.yaml` — профиль format 2 из `acceptance.yaml.in`;
- `02-installer/sut` — обёртка вызова `sut.py` с бэкендом, выгрузкой и интерпретатором.

Профиль задаёт `stand.load`, `stand.canonical`, `adapters.load` и `vectors` трёх пакетов. `manifest-put` в нём нет:
ему нужно хранилище урока 1, а у SUT его нет.

## Протокол

| Команда | Вход | Выход |
|---|---|---|
| `load {file}` | файл манифеста | код 0 — принят; код 2 — отказ, текст на stderr; иной код — авария |
| `load-adapter` | строки stdin — пути файлов | на каждую — строка JSON `{"verdict": "ok"\|"refused", "text": …}` |
| `canonical {input}` | файл манифеста | stdout — байты вида (JCS, без перевода строки); отказ — код 2 и текст |
| `vectors {input}` | файл — рамка запроса | stdout — рамка ответа, код 0 |

Текст отказа один для `load`, адаптера и `canonical`:
`refused:<класс>: <имя файла>: at <путь JSON-массивом>[ <путь>…][ line N…]`. Класс у `v7` — слой (`text`, `form`,
`relations`); у `dialect` — класс диалекта (`text`, `key`, `value`, `reference`, `name`). Пути — по `path_style:
json`, номера строк есть только у `dialect`.

Рамка запроса: `{"format": 1, "package", "table", "case", "variant", "cells": {колонка: ячейка}, "files": {имя:
base64}}` (`c_vector_protocol.encode_request`). Рамка ответа: `{"exit_code", "stdout_b64", "stderr_b64"}` — код и
байты пакета. Колонки ожидания (`verdict`, `paths`, `outcome`, `expect`, `layer1`, `rule`) SUT не читает. Ответы
пакетов:

| Пакет | Вход из `cells` и `files` | Ответ пакета |
|---|---|---|
| `02-installer/canonical` | `input` — путь манифеста от корня выгрузки; байты — `files.input` или файл выгрузки | код 0, stdout — байты вида; отказ — код 2, stderr — текст отказа |
| `common/family-read` | `family`, `kind`, `mode`, `who` (JSON-массив ролей), `text` | код 0, stdout — JSON `{"verdict", "paths", "outcome"}`; `outcome` — у писателя `[]`, у читателя `{роль: [пути строк outcomes.tsv]}` по каждой роли `who`; строго — все три |
| `common/yaml-suite` | `id`; вход — `files["in.yaml"]` или `inputs/<id>.yaml` пакета | код 0, stdout — JSON `{"layer1": "ok"\|"refused", "rule"}`; строго — только `layer1` (вердикт слоя 1, без уточнения), `rule` — подсказка, как `diagnostics.tsv` |

Авария внутри пакета — код пакета 1, причина на stderr. Внешний код команды — 0.

# Стенд В7: версии и выбор

Закреплено для генератора В7 и наборов А, Б (ADR-0092 п. 9: стандарт, внешний набор тестов, закреплённая версия).
Python — `requirements.txt` (с хешами колёс macOS arm64), Go — `go/go.mod` и `go/go.sum`.

| Что | Версия | Внешний набор | Почему |
|---|---|---|---|
| CPython | 3.12.15 (`/opt/homebrew/bin/python3.12`) | — | интерпретатор курса и раннера |
| Python JSON Schema | `jsonschema` 4.26.0 (Draft 2020-12) | JSON-Schema-Test-Suite, Bowtie | мерили записка, Kimi, Claude; известный дефект — `$` перед последним `\n` (`re.search`) — слой 5 |
| Python CEL | `cel-expr-python` 0.1.3 (ядро cel-cpp, Google) | cel-spec conformance (cel-cpp) | 270/270 на связях у Claude и Gemini; расширение strings (`split`) есть |
| Go | go1.22.10 (`go 1.22.0`, `toolchain go1.22.10`) | — | тот же язык, что `cammeta-c-go` (`go 1.22`); без скачивания тулчейна |
| Go JSON Schema | `github.com/santhosh-tekuri/jsonschema/v6` v6.0.2 | JSON-Schema-Test-Suite, Bowtie | мерил Claude; известный дефект — `propertyNames` без места в экземпляре — слой 4; regexp — RE2 |
| Go CEL | `github.com/google/cel-go` v0.26.1 (`cel.dev/expr` v0.24.0) | cel-spec conformance | эталонная реализация CEL; последняя, что собирается на go 1.22 (v0.26.1: `go 1.22.0`); 270/270 у Claude |
| Python YAML (слой 1) | `ruamel.yaml` 0.19.1 (pure, YAML 1.2, события) | yaml-test-suite | YAML 1.2 (PyYAML — 1.1); события дают стиль узла, якорь, тег и метки начала и конца; на нём эталонный textlayer — тот же парсер у эталона и у В7 |
| Go YAML (слой 1) | `go.yaml.in/yaml/v3` v3.0.5 | yaml-test-suite | продолжение `gopkg.in/yaml.v3` (архив) под организацией YAML, API тот же (узлы: стиль, якорь, тег, строка, колонка); `goccy/go-yaml` — иной API, на корпусе не мерился |
| yaml-test-suite | `data-2022-01-17` (архив тега, sha256 `ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256`) | — | последний тег данных набора; распакован в `/Users/murat/w2c/v7-stand/yts/` |

**Отклонено:** `cel-python` (celpy) 0.5.0 — падает на 22 из 270 случаев связей (`IndexError` в разборе, строка 4 —
ревью Claude), нет двуместных макросов, `1 == 1.0` — ошибка, `true == 1` — истина (ревью Kimi); поручение называло
«cel-python» — взят CEL для Python от Google. `cel-go` v0.33.0 требует тулчейн новее go 1.22.

Стенд вне репозитория: `/Users/murat/w2c/v7-stand/venv` (Python), модули Go — в `GOMODCACHE` пользователя.

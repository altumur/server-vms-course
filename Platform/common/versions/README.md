# Закреплённые версии

Библиотеки стандарта и парсеры YAML, на которых реализации исполняют слои В7 ([слои В7](../LAYERS.md)): закреплённая
версия — стандарт, внешний набор тестов и известные дефекты этой версии (ADR-0092 п. 9). Python — [`requirements.txt`](requirements.txt)
(хеши — колёса macOS arm64; на Linux — те же версии с хешами колёс своей платформы), Go — [`go.mod`](go.mod) и
[`go.sum`](go.sum) (только требования модулей; имя модуля нейтральное, реализация ставит своё).

| Что | Python | Go | Внешний набор тестов |
|---|---|---|---|
| язык | CPython 3.12.15 | Go 1.22 (`go 1.22.0`, `toolchain go1.22.10`) | — |
| JSON Schema 2020-12 (форма) | `jsonschema` 4.26.0 | `github.com/santhosh-tekuri/jsonschema/v6` v6.0.2 | JSON-Schema-Test-Suite |
| CEL (связи) | `cel-expr-python` 0.1.3 | `github.com/google/cel-go` v0.26.1 (`cel.dev/expr` v0.24.0) | cel-spec conformance |
| YAML 1.2 (слой 1) | `ruamel.yaml` 0.19.1 | `go.yaml.in/yaml/v3` v3.0.5 | yaml-test-suite |

**yaml-test-suite** — тег данных `data-2022-01-17`, архив
`https://github.com/yaml/yaml-test-suite/archive/refs/tags/data-2022-01-17.tar.gz`, sha256
`ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256`; входы и исходы слоя 1 —
[пакет `yaml-suite`](../vectors/yaml-suite/README.md).

**Известные дефекты** закреплённых версий и их обходы — [слои В7](../LAYERS.md): § 3 «Выражение» (полное совпадение
`pattern`), § 4 (D13, D16), § 5 (ошибка исполнения CEL, порядок перебора отображения D18), § 2 слой 4 (место отказа
`propertyNames`, `uniqueItems`).

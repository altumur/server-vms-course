# Pinned versions

This English text is the source; the Russian translation `ru/versions/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The standard libraries and the YAML parsers on which the implementations execute the layers of В7 ([the layers of В7](../LAYERS.md)): the pinned
version is the standard, the external test suite and the known defects of this version (ADR-0092 item 9). Python — [`requirements.txt`](requirements.txt)
(the hashes are of macOS arm64 wheels; on Linux — the same versions with the hashes of the wheels of its own platform), Go — [`go.mod`](go.mod) and
[`go.sum`](go.sum) (only the requirements of the modules; the module name is neutral, the implementation sets its own).

| What | Python | Go | External test suite |
|---|---|---|---|
| language | CPython 3.12.15 | Go 1.22 (`go 1.22.0`, `toolchain go1.22.10`) | — |
| JSON Schema 2020-12 (the form) | `jsonschema` 4.26.0 | `github.com/santhosh-tekuri/jsonschema/v6` v6.0.2 | JSON-Schema-Test-Suite |
| CEL (the relations) | `cel-expr-python` 0.1.3 | `github.com/google/cel-go` v0.26.1 (`cel.dev/expr` v0.24.0) | cel-spec conformance |
| YAML 1.2 (layer 1) | `ruamel.yaml` 0.19.1 | `go.yaml.in/yaml/v3` v3.0.5 | yaml-test-suite |
| cryptography (AES-GCM, Ed25519/X25519, X.509, CRL; only `lib/w2cforms` per the contracts `common/contracts`) | `cryptography` 50.0.2 (`cffi` 2.1.1, `pycparser` 3.11) | the standard library | the external test suite of the project (ADR-0092 addendum 2026-10-29) |

**yaml-test-suite** — the data tag `data-2022-01-17`, the archive
`https://github.com/yaml/yaml-test-suite/archive/refs/tags/data-2022-01-17.tar.gz`, sha256
`ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256`; the inputs and outcomes of layer 1 —
[the package `yaml-suite`](../vectors/yaml-suite/README.md).

**Known defects** of the pinned versions, their workarounds and vectors — [DEFECTS.md](DEFECTS.md); where a workaround stands in the layers — [the layers of В7](../LAYERS.md): § 3 «Expression» (the full match
of `pattern`), § 4 (D13, D16), § 5 (a CEL execution error, the map iteration order D18), § 2 layer 4 (the place of refusal of
`propertyNames`, `uniqueItems`).

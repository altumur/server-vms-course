# Pinned versions

This English text is the source; the Russian translation `ru/versions/README.md` (for people, not in the export) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The standard libraries and the YAML parsers on which the implementations execute the layers of V7 ([the layers of V7](../LAYERS.md)): the pinned
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

A module of the pinned [`go.mod`](go.mod) that the main module of a Go implementation uses is taken only by a `require` directive with the pinned version and the checksums of [`go.sum`](go.sum), from the module cache that the stand provides ([build](../acceptance/PROFILE.md#command-ownership-and-build-results)). The implementation tree holds no copy of the sources of these modules, its `go.mod` has no `replace` directive of them, and the root of the main module holds no `vendor` directory and no `go.work`.


## Shared code module pins

The modules in [the shared code inventory](../modules.md) use direct requirements in this same `go.mod` and checksums in `go.sum`. Their pins are added after generation and qualification of those modules. Until then, a consuming lesson is not ready for generation; this inventory does not invent a version or select a commit.

## Raft library and implementation boundary

The Go implementation of the P/01 Raft group uses the direct dependency `github.com/hashicorp/raft v1.7.3` in [`go.mod`](go.mod), with its checksums in [`go.sum`](go.sum). The model implements the FSM, I/O and adapters around this library; it does not implement a new consensus core. This library choice does not add an external platform protocol.

The adapters remain responsible for the durable `LogStore` and `StableStore`, mTLS peer identity, atomic FSM application, admission time and replay state, snapshots and recovery, error outcomes, cancellation and orderly shutdown under the P/01 norms. Snapshot persistence must respect the library's concurrent FSM contract. Using Raft alone proves neither durability nor production readiness; the cost, lock and failure obligations remain with the implementation.

The [pinned upstream module](https://raw.githubusercontent.com/hashicorp/raft/v1.7.3/go.mod) declares Go 1.20. The existing `go 1.22.0` and `toolchain go1.22.10` stay unchanged. The [release](https://github.com/hashicorp/raft/releases/tag/v1.7.3) and [FSM API](https://raw.githubusercontent.com/hashicorp/raft/v1.7.3/fsm.go) identify this dependency, not a substitute for the platform norms. Packaging must include its complete runtime dependency closure, module versions, checksums, licenses and provenance, and verify an isolated build from the module cache of the stand without network access. This Source pin does not claim that the offline check has been delivered.

**yaml-test-suite** — the inputs and outcomes of layer 1 — [the package `yaml-suite`](../vectors/yaml-suite/README.md).

**Known defects** of the pinned versions, their workarounds and vectors — [DEFECTS.md](DEFECTS.md); where a workaround stands in the layers — [the layers of V7](../LAYERS.md): § 3 «Expression» (the full match
of `pattern`), § 4 (D13, D16), § 5 (a CEL execution error, the map iteration order D18), § 2 layer 4 (the place of refusal of
`propertyNames`, `uniqueItems`).

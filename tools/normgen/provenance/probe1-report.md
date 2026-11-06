# Code origin: ADR-0127 probe

Implementation: `probe1` / `ec3ea7a2ec155995c3990f4bd37e23ead8005af2`.

Snapshots are read from Git; working trees and file headers are excluded. Count LF lines plus a final
nonempty unterminated line, including comments and blanks. An unchanged editable SHA retains manifest origin;
a changed editable file is entirely model-owned by final bytes. A changed closed file is an error.

| Scope | generated | handwritten kit | model | total |
|---|---:|---:|---:|---:|
| Code | 10107 | 8213 | 12481 | 30801 |
| Tests | 29312 | 0 | 39 | 29351 |

Included directories: `01-store`, `02-installer`, `03-worker`, `04-controller`, `05-resource`, `06-console`.
Excluded directory names at any depth: `vendor`.
Additional excluded paths: none.
Suffixes: `.go`; tests: `_test.go`.

| Directory, code excluding tests | generated | handwritten kit | model |
|---|---:|---:|---:|
| `01-store` | 7361 | 3339 | 2436 |
| `02-installer` | 1172 | 2413 | 4088 |
| `03-worker` | 1574 | 2461 | 5948 |
| `04-controller` | 0 | 0 | 3 |
| `05-resource` | 0 | 0 | 3 |
| `06-console` | 0 | 0 | 3 |

Kit pins are import commits containing the manifest and kit bytes verified against its SHA-256 entries.

- `p01-en-cfcef1d0`: `probe1` / `66afb11a674fca604f36be57045d492c48827acd`; manifest `kit.manifest.json`;
  SHA-256 `4a7e70aa9131fdea9d760e4e3a40b9054445a254e310f1b7c3a15ee4ad038c82`; course `c80d17073b0e7b641a21008677bab9daf6b35ef4`, export `cfcef1d02031ca949798d12cd707fff7b6c2db98`.
- `p02-en-c9eaf7f0`: `probe1` / `9bc53b3ee8135d4d584fe744fa195fcd87f6bfc5`; manifest `kit-p02.manifest.json`;
  SHA-256 `c2908b2d3fb818aa69f058311985ab7a33b58988e00a1801d63d6d3cca33290f`; course `94fedb8b15bddd37b4a0c90502af57bb60165833`, export `c9eaf7f0a41e954bb1c32bc9ca5d20c6795c2173`.
- `p03-en-c9eaf7f0`: `probe1` / `fab6ddfb7cc8b024b51082842301fc4d377b525b`; manifest `kit-p03.manifest.json`;
  SHA-256 `eb2de89f35e991a85f84c16f719eb27c57e4ace9de7eed146286f9e2000c19f8`; course `fd97e6c17dbf109ab47ec7eabb532afddac8812c`, export `c9eaf7f0a41e954bb1c32bc9ca5d20c6795c2173`.

Editable files still byte-identical to the kit:

- `01-store/internal/coreadapter/open.go`: 17 lines, `generated` (SHA matched).

Missing kit files within the selected scope: 0.
JSON output records each file's final SHA-256, Git blob, line count and classification reason.

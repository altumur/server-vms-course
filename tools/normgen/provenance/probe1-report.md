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

## Original recorded output

The English text above translates a historical Russian report. It is not a newly observed English run and does not
inherit the original report hash. No implementation was reread or recounted for this translation.

The complete immutable original is `6d399cf1302a9846e709f1c9ecb9350339541803:tools/normgen/provenance/probe1-report.md` (Git blob `eac1315a545a6f06a0b2a70b5c146eec51c14edd`),
SHA-256 `e6afa45f3731f1211b5083dba7b171c57c0d831c0a3d3152f0e1632471e82942`. Retrieve it with:

```sh
git show 6d399cf1302a9846e709f1c9ecb9350339541803:tools/normgen/provenance/probe1-report.md
```

Exact original stdout excerpt (the first 13 LF lines, encoded as one JSON string; decoding restores the original UTF-8
bytes, including the final LF):

```json
"# \u041f\u0440\u043e\u0438\u0441\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u0435 \u043a\u043e\u0434\u0430: \u043f\u0440\u043e\u0431\u0430 ADR-0127\n\n\u0420\u0435\u0430\u043b\u0438\u0437\u0430\u0446\u0438\u044f: `probe1` / `ec3ea7a2ec155995c3990f4bd37e23ead8005af2`.\n\n\u0421\u043d\u0438\u043c\u043a\u0438 \u0447\u0438\u0442\u0430\u044e\u0442\u0441\u044f \u0438\u0437 Git; \u0440\u0430\u0431\u043e\u0447\u0435\u0435 \u0434\u0435\u0440\u0435\u0432\u043e \u0438 \u0448\u0430\u043f\u043a\u0438 \u0444\u0430\u0439\u043b\u043e\u0432 \u043d\u0435 \u0443\u0447\u0430\u0441\u0442\u0432\u0443\u044e\u0442. \u0421\u0442\u0440\u043e\u043a\u0430 \u2014 LF, \u043f\u043b\u044e\u0441 \u043f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f\n\u043d\u0435\u043f\u0443\u0441\u0442\u0430\u044f \u0441\u0442\u0440\u043e\u043a\u0430 \u0431\u0435\u0437 LF; \u043a\u043e\u043c\u043c\u0435\u043d\u0442\u0430\u0440\u0438\u0438 \u0438 \u043f\u0443\u0441\u0442\u044b\u0435 \u0441\u0442\u0440\u043e\u043a\u0438 \u0432\u043a\u043b\u044e\u0447\u0435\u043d\u044b. \u0421\u043e\u0432\u043f\u0430\u0432\u0448\u0438\u0439 SHA editable \u0441\u043e\u0445\u0440\u0430\u043d\u044f\u0435\u0442 origin\n\u043c\u0430\u043d\u0438\u0444\u0435\u0441\u0442\u0430; \u0438\u0437\u043c\u0435\u043d\u0451\u043d\u043d\u044b\u0439 editable \u0446\u0435\u043b\u0438\u043a\u043e\u043c \u043e\u0442\u043d\u043e\u0441\u0438\u0442\u0441\u044f \u043a \u043c\u043e\u0434\u0435\u043b\u0438 \u043f\u043e \u043a\u043e\u043d\u0435\u0447\u043d\u044b\u043c \u0431\u0430\u0439\u0442\u0430\u043c. \u0418\u0437\u043c\u0435\u043d\u0451\u043d\u043d\u044b\u0439 \u0437\u0430\u043a\u0440\u044b\u0442\u044b\u0439 \u0444\u0430\u0439\u043b \u2014 \u043e\u0448\u0438\u0431\u043a\u0430.\n\n| \u0421\u043e\u0441\u0442\u0430\u0432 | generated | handwritten \u043f\u0430\u043a\u0435\u0442\u0430 | \u043c\u043e\u0434\u0435\u043b\u044c | \u0432\u0441\u0435\u0433\u043e |\n|---|---:|---:|---:|---:|\n| \u041a\u043e\u0434 | 10107 | 8213 | 12481 | 30801 |\n| \u0422\u0435\u0441\u0442\u044b | 29312 | 0 | 39 | 29351 |\n\n"
```

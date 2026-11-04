# yaml-suite vectors: layer 1 on yaml-test-suite (ADR-0092 item 2; set «Б», the section «слой 1 сужает YAML 1.2.2»)

This English text is the source; the Russian [`README.md`](../README.md) is derived from it by translation and is not edited by hand (ADR-0121; ADR-0124 addendum (1) item 4).

The source is yaml-test-suite (github.com/yaml/yaml-test-suite), the data of the tag `data-2022-01-17`: the archive
`https://github.com/yaml/yaml-test-suite/archive/refs/tags/data-2022-01-17.tar.gz`, sha256
`ccae49c1d010d27c20d315969a97752f95b14642fc1e73755db4eb2df4bb0256`. The licence is MIT, the full text is `LICENSE` (the file
`License` of the repository, the tag `v2022-01-17`, sha256 `c9562189164244554a69ab3f29d2d93ed9492c165723aaaa5fffc932cdbbfc85`).
The acceptance runs without a network: the inputs are in the package, `inputs/<id>.yaml` — the bytes of the `in.yaml` of a test (402 files; an `id` with `/` — a subdirectory).
`expect.tsv`: `id<TAB>suite<TAB>layer1<TAB>rule`:
- `id` — the path of the test directory in the archive, the input — `inputs/<id>.yaml`;
- `suite` — the expectation of the suite: `error` (the input is outside YAML 1.2.2) or `ok`;
- `layer1` — the outcome of layer 1 of the manifest (the YAML 1.2.2 parser and the thin check of Н1.1): `ok` or `refused`; `refused` at
  `suite` = `ok` — a narrowing of YAML 1.2.2 by the norm (a rule of the thin check or an input outside the subset of Н1.1), approved
  by set «Б»;
- `rule` — the rule of the thin check that refused first (`parser` — a refusal of the parser; `-` — at `ok`); a hint, not a norm.
The answer of an implementation to a row is the JSON `{"layer1": "ok"|"refused"}`, optionally with `"rule"`: only
`layer1` is compared strictly (anything else is red, ADR-0092 item 2); `rule` is a hint, like the `diagnostics.tsv` of the corpus: into the report, without a failure
(the rule names of an implementation are its own; the list of the rules of the thin check is `common/LAYERS.md`).

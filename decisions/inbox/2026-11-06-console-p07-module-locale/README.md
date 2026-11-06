# P/07 module and localization: deterministic byte conversion

Authorization: coord103, ADR-0121 addendum (10), bounded materialization scope.
Base: `e07b32a5030c696d89c72444e760a86f6246c487`.

The only runtime source changes are three new files under
`Platform/07-console-module/module/console.{js,css,html}` and the exact move of
`Platform/06-console/data/localization.tsv` to `Platform/07-console-module/data/localization.tsv`.
This directory contains conversion tooling, the English comment map and author evidence.
It is outside the exported lesson and is not a second editable word dictionary.

## Conversion and reproduction

Requires Node.js 22 and the pinned Acorn dependency in `package-lock.json`.
Run from this directory:

```sh
npm ci --ignore-scripts --no-audit --no-fund
npm run check
```

`convert.mjs --write` recreates all three canonical files from the immutable witnesses,
the single canonical TSV and `comments.json`; it also recreates `map.json` and `evidence.json`.
For the first migration from the base only, it reads the historical P/06 TSV, writes its identical
bytes at P/07 and removes the old path. It never writes `Source/`.

The converter rejects duplicate, extra or missing TSV keys, a changed language value or substitution
parameter, or a change to the table's exact bytes. It preserves significant whitespace instead of
trimming columns. This artifact deliberately describes the bounded 519-key migration, not a general
future procedure for changing the word roster.

`--check` performs no writes. It recomputes the expected files, verifies the actual files byte for byte
and rejects stale evidence. `reproduction.json` records a repeated `--write`: all six outputs
(three module files, the TSV, the map and the evidence) had identical SHA-256 before and after.
On the committed branch, another `--write` followed by `git diff --exit-code` for those six paths
must leave no difference.

## Runtime loading

The canonical TSV is the sole editable localization source. The internal `WORDS` object in the
published JS is its generated projection. English values stay English; only the RU projection
uses Unicode escapes. No Cyrillic character is present in the three new module files.

The browser still loads `/platform/console.js?v=1` synchronously. Only the existing exact
`opts.lang: "ru"` selects Russian; omitted `lang`, `en`, `RU` and `ru-RU` select English.
No locale fetch, endpoint, URL alias, storage preference, public API, feature or version is added.

## Parity and permitted behavior change

The author verifier uses Acorn 8.15.0 / ES2022 to parse the witness and new module. Exactly two AST
subtrees are replaced with comparison markers: the `WORDS` initializer and the `W` language selector.
The target selector is separately required to match the approved expression. Every other AST node
and raw noncomment token must match. Comment changes therefore cannot hide another behavior change.
CSS bytes outside comments match; HTML markup and inline JS tokens match outside comments.

The verifier decodes literal properties without executing the module. It compares the complete
519-key EN/RU leaf rosters against both the TSV and effective witness values. Dotted event names remain
whole keys of `kinds`; `n` is the other nested object. Every substitution name and occurrence count is
preserved. Duplicate witness properties use their final value; generated properties have no duplicates.
The final `glass` values and final U+0020 in both `loginAt` captions are preserved exactly.

Six rejection probes cover an extra key, missing key, duplicate key, changed parameter, trimmed
`loginAt` and a code-token change outside the approved holes. The language expression is exercised
against explicit languages and a Russian browser setting.

`fmt` and `fmtDay` are byte-identical expressions to their witnesses. Their scope is pending spec103;
this delivery changes neither formatter, timezone nor protocol time. C6, A1, folder writes, `ifMatch`,
other module debts and the public API are outside this delivery.

## Evidence and integration

- `comments.json`: 31 source-line hashes and English comment replacements; no old dictionary copy.
- `map.json`: every TSV key maps to its witness/canonical literal lines, decoded-value hashes and parameters.
- `evidence.json`: immutable witness hashes, canonical hashes, AST/token parity, locale matrix, negative
  probes, unchanged formatters and the new inline CSP hash.
- `reproduction.json`: byte-identical repeated conversion.

These are author checks, not review103's independent judge or the full CT 103 GATE.
spec103 owns norm/acceptance/jsdom reference activation. coord103 owns export/integration; review103 owns
the independent judge and Cyrillic exception relocation. Until their activation, old readers still point
at the removed P/06 locale or the immutable witness. This byte branch does not claim to close those tasks.

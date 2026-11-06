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

The author verifier uses Acorn 8.15.0 / ES2022 to parse the witness and new module. Exactly four areas
are exempted: the `WORDS` initializer, the `W` language selector, the `fmt` declaration moved into `mount`,
and the `fmtDay` initializer. The moved `fmt` declaration is removed from both comparison streams;
its exact target shape and position immediately after `mount`'s `W` are checked separately.
The selector and both formatter expressions must match their exact approved shapes. Every other AST
node and raw noncomment token must match. Comment changes cannot hide another behavior change.
CSS bytes outside comments match; HTML markup and inline JS tokens match outside comments.

The verifier decodes literal properties without executing the module. It compares the complete
519-key EN/RU leaf rosters against both the TSV and effective witness values. Dotted event names remain
whole keys of `kinds`; `n` is the other nested object. Actual property-path arrays are also compared,
so a generic dot split cannot masquerade as the same flattened key. All other 477 keys stay at the root.
Every substitution name and occurrence count is
preserved. Duplicate witness properties use their final value; generated properties have no duplicates.
The final `glass` values and final U+0020 in both `loginAt` captions are preserved exactly.

Eight rejection probes cover an extra key, missing key, duplicate key, changed parameter, trimmed
`loginAt`, a code-token change outside the approved areas, an added timezone and a generic event-name
dot split. The language expression is exercised
against explicit languages and a Russian browser setting.

The formatter extension was approved by coord103 after spec103's decision. `fmt` is inside each `mount`;
both formatters use that mount's already selected `W`: explicit RU gives `ru-RU`, otherwise `en-US`.
`fmt` still has no formatting-options argument. `fmtDay` keeps day/month/hour/minute `2-digit` and
`hour12: false`. There is no `timeZone` option. The `t * 1000`, falsy-input dash and constructor behavior
are preserved. Thirty-two formatter probes interleave EN/RU mounts, also after the caller mutates its
original opts object, and check the exact locale, milliseconds and option arguments.
Timezone and protocol time are unchanged. C6, A1, folder writes, `ifMatch`,
other module debts and the public API are outside this delivery.

## Evidence and integration

- `comments.json`: 31 source-line hashes and English comment replacements; no old dictionary copy.
- `map.json`: every TSV key maps to its witness/canonical literal lines, decoded-value hashes and parameters.
- `evidence.json`: immutable witness hashes, canonical hashes, AST/token parity, locale matrix, negative
  probes, exact formatter scope/arguments and the new inline CSP hash.
- `reproduction.json`: byte-identical repeated conversion.

These are author checks, not review103's independent judge or the full CT 103 GATE.
spec103 owns norm/acceptance/jsdom reference activation. coord103 owns export/integration; review103 owns
the independent judge and Cyrillic exception relocation. Until their activation, old readers still point
at the removed P/06 locale or the immutable witness. This byte branch does not claim to close those tasks.

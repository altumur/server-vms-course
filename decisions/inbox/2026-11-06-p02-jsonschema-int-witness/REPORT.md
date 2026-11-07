# P/02: correct the embedded JSON Schema integer witness

This is a normal child of `dffe58fef31f365256a043449e9e846f8972560e`, authorized separately by coord103 under the existing ADR-0129 (11) assignment. It corrects an erroneous example, not the norm, parser, vocabulary or generator. The old published slice, its map/report/check failure and all external receipts remain historical and unchanged.

The example introduced through `82f0baba28ba6f39e10e4038a4faca179d9eb2f8` confused the native manifest field kind `int` with the JSON Schema2020-12 type `integer` inside `unit.state`. Only `/unit/state/cursor/properties/at/type` and `/unit/state/progress/properties/done/type` change, from `int` to `integer`, in both the YAML input and its canonical expected JSON. Every other parsed value, ordering, formatting and final-LF state is preserved. The native `unit.fields.start.type=int`, its default and canonical field entry remain byte-identical; snapshot remains unchanged. No alias is accepted.

Own checks on the unchanged strict parent schema:

- Both old state schemas are rejected by the standard2020-12 metaschema; both corrected state schemas are accepted.
- The existing V7 loader rejects the old input as form at those two paths, accepts the corrected input, and produces exactly the corrected1472byte canonical expectation, SHA-256 `6e3c7fc871f17ff173ed0a1dbef3bdf306c54b5b2221869bda33fefff70e22c4`.
- The existing type17 negative example remains refused:form. Native field-kind int remains unchanged in both input and canonical result.
- `cases.tsv` and its complete220-case identity set are byte-identical; the other233 tracked canonical files and all other Platform paths remain unchanged against the parent. No ordinary947/402 corpus, schema, form, selector, old expectation or success result is reclassified.

Exact paths, four pointer changes, before/after SHA-256 values, authorization hashes and source-only evidence are in `source-map.json`, `author-check.json` and `four-token.diff`. These are reference source/canonical checks, not implementation execution. No normgen/KIT/Go/runner/SUT/export/pin is run or changed. Full integration/GATE remains coord103's task. The existing structural source check now passes with62exceptions, canonical_vectors220; standard Cyrillic shrink also passes without changing its debt registry. Log hashes are recorded in `author-check.json`. These results do not close either open obligation or establish lesson readiness.

B1 full positive-profile sufficiency and executable recovery remain **OPEN**. Neither this correction nor a green structural source check would make the lesson ready or execute its recovery scenario.

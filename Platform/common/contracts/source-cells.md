# Source-only TSV string encoding

ADR-0121 addendum (6), decision of the Architect, 2026-11-06. This is a source form shared by generators and runner readers. It adds no native command, runtime alias or protocol value.

## Declaration

A table may have exactly one declaration line, before its header and first data row. Its exact grammar is:

```text
declaration = "# cell-json: " name *( "," name )
name = ( ALPHA / "_" ) *( ALPHA / DIGIT / "_" )
ALPHA = %x41-5A / %x61-7A
DIGIT = %x30-39
```

The declaration occupies the whole physical line. There is exactly one ASCII space after the colon, no spaces around commas, no indentation and no trailing spaces. Names are unique and name existing columns. Duplicate table header names are invalid. The ordinary first nonempty, noncomment line is the header. A headerless table gets its names from the existing `header` field in [wire.tsv](../vectors/wire.tsv): the leading `-` declares headerless input and is not a column. Its first data row is retained. No new header row is inserted.

## Cells and decoding

Every data cell of every declared column is an ASCII strict JSON string, including an empty value as `""`. A non-ASCII character uses a JSON Unicode escape; a character outside the basic multilingual plane uses a valid surrogate pair. Invalid JSON, a JSON value other than a string, an unpaired surrogate, a duplicate declaration or column, an unknown name, or a row with the wrong width is a form error. Encoding some cells of a declared column and leaving others raw is invalid. Undeclared columns are unchanged.

The common reader decodes each declared source cell exactly once, before any wire, CEL or native interpretation, and encodes the resulting string as UTF-8. It never decodes that string recursively. For example, source `"\\u0436"` produces the six literal ASCII characters `\u0436`; source `"\u0436"` produces one Unicode scalar. A later JSON interpretation required by an existing column's wire form is unchanged; it is separate from this source step. Comments are not data and the marker is not sent to the implementation. No request, case identifier or physical source line number changes.

## Preservation and conformance

[cell-json-sha256.tsv](../data/cell-json-sha256.tsv) covers every declared data cell exactly once by table path, physical line and column. `before_sha256` hashes the original cell's UTF-8 bytes at the recorded baseline; `decoded_sha256` hashes the UTF-8 bytes after the single source decode. Both hashes must match each other and the decoded cell. Missing, duplicate and extra proof rows are form errors. Thus raw JSON text, JCS, AAD, signature inputs, envelopes and expected outputs retain their original bytes.

[The conformance fixtures](../vectors/source-cells/cases.json) specify valid and invalid declarations and cells, positional input, first-row retention, surrogate pairs and single decoding. They test this source form and introduce no runtime surface. `en_mirror` and `check_spec` judge the form and complete byte proof; generator and runner readers use the same source rule.

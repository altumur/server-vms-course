# Course-owned loader verdict witnesses

This English text is the source; the Russian translation `ru/acceptance/1/spec_verdicts/README.md` (for people, not in the export) is derived from it and is not edited by hand (ADR-0121; ADR-0124).

This package contains [`spec_verdicts.tsv`](spec_verdicts.tsv) and the same-directory `<case>.subsystem.yaml` inputs: 138 cases, 19 `ok` and 119 `refused`. The initial files are byte-identical to the accepted joint's Source witnesses. This package does not replace the 947-case lesson corpus or the 220 canonical-view vectors.

The TSV is UTF-8 with LF and TAB separators. It has no header: skip empty lines and lines starting with `#`; every remaining row is exactly `case<TAB>verdict`. Each case names exactly one file beside the table, and every input file has exactly one row. Keep the first data row and the published order.

Read the YAML inputs as raw bytes. BOM, invalid UTF-8, NUL, duplicate keys and depth witnesses are intentional negative inputs; a copy must not decode, normalize or repair them. The verdicts retain their existing meanings and introduce no loader refusal class or native command.

The course owns this package independently of the product (ADR-0083 addendum (115)). Imported header comments are historical provenance, not a synchronization contract. Old `Source/tests/testdata` copies remain immutable witnesses.

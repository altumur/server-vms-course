# Judge-only protocol case data

This English text is the source; the Russian translation `ru/vectors/journal/README.cases.md` is derived from it (ADR-0121).

Generic protocol rules remain in [README.md](README.md). The following original mixed paragraph preserves the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

The same file rules; the header `case<TAB>file<TAB>line<TAB>expect<TAB>note`: `file` is the content of the bucket before the write,
`line` is the new line without LF, `expect` is the content after the write (JSON strings) or `@refuse` — a refusal of the write, the file does not
change (deeper than `JSON_DEPTH`, `depth-129`; EJ-DEPTH-BASELINE33). A tail without LF is completed with LF, there is no truncation
(EJ-L03); the bucket `no-final-lf` read after the write gives `garbled` 1, and `json-tail` — three ordinary lines (`tail-json-appended` in `bucket.tsv`; EJ-L06).

End of judge-only protocol case data.

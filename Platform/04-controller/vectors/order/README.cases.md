# Judge-only protocol case data

This English text is the source; the Russian translation `ru/vectors/order/README.cases.md` is derived from it (ADR-0121).

Generic protocol rules remain in [README.md](README.md). The following original mixed paragraph preserves the existing named case associations as judge-only provenance.

<!-- original-mixed-case-paragraph -->

The aggregate waiting/sets[].waiting keeps integer-by-value spellings, but has no common.uint53 ceiling or binary64/int64 conversion. Compute sums and ceil division exactly; individual weight/capacity and all other input domains remain unchanged. The separate adr15-waiting-max53/at53/odd53 inputs are 2^53-1, 2^53 and 2^53+1; with per=2^52 they need two, two and three processes. These are added rows, never a reinterpretation of old cases.


End of judge-only protocol case data.

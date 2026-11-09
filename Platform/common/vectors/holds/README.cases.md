# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/holds/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

38 rows: 11 `held`, 12 `not_held`, 15 `unknown`. The window — the ends inclusive (touching `since` by the end of the bucket and `until`
by the beginning), `float` with a fractional second at both ends, `int` with the notation `.0` and with a fraction; `longest` shorter and longer than the window;
`until = since` and `until < since`; `released` non-empty, `0` at an `int` field, empty, without an element, not declared, over unreadable
fields; `unit` without an element, empty, with spaces (as is); `since`/`until` without an element, not reading as their type, with the sign
`-` or `+` and with an exponent (not of the form of the reader `time` of the codec), a field of a non-numeric type; an incomplete declaration; an undecoded row; a manifest without `holds`.

End of judge-only case data.

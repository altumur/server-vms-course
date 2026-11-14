# Judge-only case data

This English text is the source; the Russian translation `ru/vectors/log-mask/README.cases.md` is derived from it (ADR-0121).

Generic rules remain in [README.md](README.md). The following original passages preserve the existing case data as judge-only provenance.

### Original passage 1

The owner is [the log mask contract](../../contracts/log-mask.md) (chapter [P/06.2](../../../06-console/spec/06.2-console.norms.md) N1.4 `never.log`; the pairs and the addresses — [the address contract](../../contracts/url-credentials.md)). The package was moved from `Platform/06-console/vectors/log-mask/` byte for byte (C06-LOG-MASK-33-01); eight rows at the end (the end of the Basic/Bearer credentials, the White_Space whitespace — the answer of «Architect» 2026-10-25) are only here: the common table `Source/tests/testdata/log_mask.tsv` is the former one.

### Original passage 2

«Specification»; the conformance of the product is by its acceptance against this table (ADR-0080 addendum 16, ADR-0083). Moved from
`Source/tests/testdata/log_mask.tsv` byte for byte (stage B, the move of lesson 6, the Architect's decision on V8 of the plan of lesson 6);
the head of the file is English, as it was: `M10/7 N1.4` in it is the former address of chapter P/06.2 N1.4.

### Original passage 3

of the contract. 33 rows: 21 masks, 12 values (fewer than three characters, a character outside the set or inside, a non-White_Space at the edge).

## UTF-8 at the end of a regex secret

The `utf8-regex-*` notes in `cases.tsv` identify cases using the existing `cam.source` path regex for `/password/<secret>` from the supplied `fields.yaml`. No field declaration or consumer route changes. These rows check [A13 and A14](../../contracts/url-credentials.md#the-address-where-the-login-and-the-password-are-in-it) through the [log mask function](../../contracts/log-mask.md#function).

The synthetic secrets `é`, `€` and `😀` end in UTF-8 characters of two, three and four bytes. Each appears literally, percent-encoded and with each percent sign escaped once more. In every spelling the whole secret becomes `***`; decoding to a fixed point does not leave a partial character or its escaping. A mixed `aé` secret followed by `/live?channel=1` also checks the last character of a longer match and byte-for-byte preservation of the surrounding log text. A path with the same Unicode characters outside a secret stays unchanged.

These are function vectors with the supplied catalogue, including at the P/01 consumer. They do not claim that the store daemon loads that catalogue or that a daemon log leak has been reproduced. Adding the rows does not execute a candidate or qualify its vector adapter.

End of judge-only case data.
